from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3
import json
import os
from datetime import datetime, timedelta
import csv
import io
import shutil

app = Flask(__name__)
app.secret_key = 'votre_cle_secrete_unique_ici_2024'  # Changez cette clé en production

# Configuration
base_dir = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(base_dir, 'candidatures.db')
BACKUP_DIR = os.path.normpath(os.path.join(base_dir, 'backups'))

def init_db():
    """Initialise la base de données avec les tables nécessaires"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    db_exists = os.path.exists(DATABASE)
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Table utilisateurs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            date_creation TEXT,
            last_login TEXT
        )
    ''')
    
    # Table candidatures
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS candidatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            position TEXT NOT NULL,
            status TEXT DEFAULT 'envoyee',
            date_envoi TEXT,
            lien_offre TEXT,
            contact_email TEXT,
            contact_phone TEXT,
            competences TEXT,
            notes TEXT,
            date_creation TEXT,
            relances TEXT,
            user_id INTEGER REFERENCES users(id)
        )
    ''')
    
    # Table certifications
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS certifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            obtention TEXT,
            expiration TEXT,
            date_creation TEXT,
            user_id INTEGER REFERENCES users(id)
        )
    ''')
    
    # Table compétences - Recréée proprement
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS competences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date_creation TEXT,
            user_id INTEGER REFERENCES users(id)
        )
    ''')
    
    # Migration sécurisée des données existantes
    try:
        cursor.execute('PRAGMA table_info(candidatures)')
        columns = [column[1] for column in cursor.fetchall()]
        if 'user_id' not in columns:
            cursor.execute('ALTER TABLE candidatures ADD COLUMN user_id INTEGER REFERENCES users(id)')
        
        cursor.execute('PRAGMA table_info(certifications)')
        columns = [column[1] for column in cursor.fetchall()]
        if 'user_id' not in columns:
            cursor.execute('ALTER TABLE certifications ADD COLUMN user_id INTEGER REFERENCES users(id)')
        
        cursor.execute('PRAGMA table_info(competences)')
        columns = [column[1] for column in cursor.fetchall()]
        if 'user_id' not in columns:
            cursor.execute('ALTER TABLE competences ADD COLUMN user_id INTEGER REFERENCES users(id)')
        
        # Créer un index unique seulement s'il n'existe pas
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_competence_user 
            ON competences(name, user_id)
        ''')
        
    except sqlite3.Error as e:
        print(f"Erreur lors de la migration : {e}")
        # Continuer malgré l'erreur
    
    conn.commit()
    conn.close()
    
    print(f"Base de données {'créée' if not db_exists else 'mise à jour'} : {DATABASE}")

def backup_database():
    """Crée une sauvegarde de la base de données"""
    if os.path.exists(DATABASE):
        backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        shutil.copy2(DATABASE, backup_path)
        
        # Garder seulement les 10 dernières sauvegardes
        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith('backup_')])
        while len(backups) > 10:
            os.remove(os.path.join(BACKUP_DIR, backups.pop(0)))

def login_required(f):
    """Décorateur pour vérifier l'authentification"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user_id():
    """Obtient l'ID de l'utilisateur connecté"""
    return session.get('user_id')

# Routes d'authentification
@app.route('/login')
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register')
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Vous avez été déconnecté avec succès', 'success')
    return redirect(url_for('login'))

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Nom d\'utilisateur et mot de passe requis'})
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, password_hash FROM users WHERE username = ? OR email = ?', 
                  (username, username))
    user = cursor.fetchone()
    
    if user and check_password_hash(user[1], password):
        session['user_id'] = user[0]
        session['username'] = username
        
        # Mettre à jour last_login
        cursor.execute('UPDATE users SET last_login = ? WHERE id = ?', 
                      (datetime.now().isoformat(), user[0]))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'redirect': url_for('index')})
    else:
        conn.close()
        return jsonify({'success': False, 'error': 'Nom d\'utilisateur ou mot de passe incorrect'})

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not username or not email or not password:
        return jsonify({'success': False, 'error': 'Tous les champs sont requis'})
    
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'Le mot de passe doit contenir au moins 6 caractères'})
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    try:
        # Vérifier si l'utilisateur existe déjà
        cursor.execute('SELECT id FROM users WHERE username = ? OR email = ?', 
                      (username, email))
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Nom d\'utilisateur ou email déjà utilisé'})
        
        # Créer le nouvel utilisateur
        password_hash = generate_password_hash(password)
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, date_creation)
            VALUES (?, ?, ?, ?)
        ''', (username, email, password_hash, datetime.now().isoformat()))
        
        user_id = cursor.lastrowid
        conn.commit()
        
        # Créer les compétences par défaut avec gestion d'erreur
        default_competences = [
            'monitoring', 'scripting', 'virtualisation', 'firewall', 'pentest', 
            'soc', 'incident-response', 'compliance', 'kubernetes', 'docker',
            'ansible', 'terraform', 'aws', 'azure', 'gcp', 'linux', 'windows',
            'python', 'powershell', 'bash', 'siem', 'forensic', 'malware-analysis'
        ]
        
        for comp in default_competences:
            try:
                cursor.execute('''
                    INSERT INTO competences (name, date_creation, user_id) 
                    VALUES (?, ?, ?)
                ''', (comp, datetime.now().isoformat(), user_id))
            except sqlite3.IntegrityError:
                # Ignorer les doublons potentiels
                continue
        
        conn.commit()
        conn.close()
        
        # Connecter automatiquement l'utilisateur
        session['user_id'] = user_id
        session['username'] = username
        
        return jsonify({'success': True, 'redirect': url_for('index')})
        
    except sqlite3.IntegrityError as e:
        conn.close()
        print(f"Erreur IntegrityError: {e}")
        return jsonify({'success': False, 'error': 'Nom d\'utilisateur ou email déjà utilisé'})
    except sqlite3.Error as e:
        conn.close()
        print(f"Erreur SQLite: {e}")
        return jsonify({'success': False, 'error': 'Erreur de base de données lors de la création du compte'})
    except Exception as e:
        conn.close()
        print(f"Erreur générale: {e}")
        return jsonify({'success': False, 'error': 'Erreur inattendue lors de la création du compte'})

# Routes principales
@app.route('/')
@login_required
def index():
    return render_template('index.html', username=session.get('username'))

# API Candidatures
@app.route('/api/candidatures', methods=['GET'])
@login_required
def get_candidatures():
    user_id = get_current_user_id()
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM candidatures WHERE user_id = ? ORDER BY date_creation DESC', (user_id,))
    
    candidatures = []
    for row in cursor.fetchall():
        candidature = {
            'id': row[0],
            'company': row[1],
            'position': row[2],
            'status': row[3],
            'dateEnvoi': row[4],
            'lienOffre': row[5],
            'contactEmail': row[6],
            'contactPhone': row[7],
            'competences': json.loads(row[8]) if row[8] else [],
            'notes': row[9],
            'dateCreation': row[10],
            'relances': json.loads(row[11]) if row[11] else []
        }
        candidatures.append(candidature)
    
    conn.close()
    return jsonify(candidatures)

@app.route('/api/candidatures', methods=['POST'])
@login_required
def add_candidature():
    data = request.json
    user_id = get_current_user_id()
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO candidatures 
        (company, position, status, date_envoi, lien_offre, contact_email, 
         contact_phone, competences, notes, date_creation, relances, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['company'],
        data['position'],
        data['status'],
        data.get('dateEnvoi'),
        data.get('lienOffre'),
        data.get('contactEmail'),
        data.get('contactPhone'),
        json.dumps(data.get('competences', [])),
        data.get('notes'),
        datetime.now().isoformat(),
        json.dumps([]),
        user_id
    ))
    
    conn.commit()
    candidature_id = cursor.lastrowid
    conn.close()
    
    backup_database()
    
    return jsonify({'id': candidature_id, 'success': True})

@app.route('/api/candidatures/<int:candidature_id>', methods=['PUT'])
@login_required
def update_candidature(candidature_id):
    data = request.json
    user_id = get_current_user_id()
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Vérifier que la candidature appartient à l'utilisateur
    cursor.execute('SELECT id FROM candidatures WHERE id = ? AND user_id = ?', 
                  (candidature_id, user_id))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'Candidature non trouvée'}), 404
    
    cursor.execute('''
        UPDATE candidatures 
        SET company=?, position=?, status=?, date_envoi=?, lien_offre=?, 
            contact_email=?, contact_phone=?, competences=?, notes=?, relances=?
        WHERE id=? AND user_id=?
    ''', (
        data['company'],
        data['position'],
        data['status'],
        data.get('dateEnvoi'),
        data.get('lienOffre'),
        data.get('contactEmail'),
        data.get('contactPhone'),
        json.dumps(data.get('competences', [])),
        data.get('notes'),
        json.dumps(data.get('relances', [])),
        candidature_id,
        user_id
    ))
    
    conn.commit()
    conn.close()
    
    backup_database()
    
    return jsonify({'success': True})

@app.route('/api/candidatures/<int:candidature_id>', methods=['DELETE'])
@login_required
def delete_candidature(candidature_id):
    user_id = get_current_user_id()
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM candidatures WHERE id=? AND user_id=?', 
                  (candidature_id, user_id))
    conn.commit()
    conn.close()
    
    backup_database()
    
    return jsonify({'success': True})

@app.route('/api/candidatures/<int:candidature_id>/relance', methods=['POST'])
@login_required
def add_relance(candidature_id):
    data = request.json
    user_id = get_current_user_id()
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Récupérer les relances actuelles
    cursor.execute('SELECT relances FROM candidatures WHERE id=? AND user_id=?', 
                  (candidature_id, user_id))
    result = cursor.fetchone()
    
    if result:
        relances = json.loads(result[0]) if result[0] else []
        relances.append({
            'date': datetime.now().isoformat(),
            'message': data.get('message', '')
        })
        
        # Mettre à jour le statut et les relances
        cursor.execute('''
            UPDATE candidatures 
            SET status='relancee', relances=?
            WHERE id=? AND user_id=?
        ''', (json.dumps(relances), candidature_id, user_id))
        
        conn.commit()
    
    conn.close()
    backup_database()
    
    return jsonify({'success': True})

# API Certifications
@app.route('/api/certifications', methods=['GET'])
@login_required
def get_certifications():
    user_id = get_current_user_id()
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM certifications WHERE user_id = ? ORDER BY date_creation DESC', 
                  (user_id,))
    
    certifications = []
    for row in cursor.fetchall():
        certification = {
            'id': row[0],
            'name': row[1],
            'obtention': row[2],
            'expiration': row[3],
            'dateCreation': row[4]
        }
        certifications.append(certification)
    
    conn.close()
    return jsonify(certifications)

@app.route('/api/certifications', methods=['POST'])
@login_required
def add_certification():
    data = request.json
    user_id = get_current_user_id()
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO certifications (name, obtention, expiration, date_creation, user_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        data['name'],
        data.get('obtention'),
        data.get('expiration'),
        datetime.now().isoformat(),
        user_id
    ))
    
    conn.commit()
    certification_id = cursor.lastrowid
    conn.close()
    
    backup_database()
    
    return jsonify({'id': certification_id, 'success': True})

@app.route('/api/certifications/<int:certification_id>', methods=['DELETE'])
@login_required
def delete_certification(certification_id):
    user_id = get_current_user_id()
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM certifications WHERE id=? AND user_id=?', 
                  (certification_id, user_id))
    conn.commit()
    conn.close()
    
    backup_database()
    
    return jsonify({'success': True})

# API Compétences
@app.route('/api/competences', methods=['GET'])
@login_required
def get_competences():
    user_id = get_current_user_id()
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM competences WHERE user_id = ? ORDER BY name', (user_id,))
    
    competences = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(competences)

@app.route('/api/competences', methods=['POST'])
@login_required
def add_competence():
    data = request.json
    user_id = get_current_user_id()
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO competences (name, date_creation, user_id)
            VALUES (?, ?, ?)
        ''', (data['name'], datetime.now().isoformat(), user_id))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        # Vérifier si c'est un doublon pour cet utilisateur
        cursor.execute('SELECT id FROM competences WHERE name = ? AND user_id = ?', 
                      (data['name'], user_id))
        if cursor.fetchone():
            success = False  # Compétence déjà existante pour cet utilisateur
        else:
            # Autre erreur d'intégrité, réessayer sans contrainte
            try:
                cursor.execute('''
                    INSERT INTO competences (name, date_creation, user_id)
                    VALUES (?, ?, ?)
                ''', (data['name'], datetime.now().isoformat(), user_id))
                conn.commit()
                success = True
            except:
                success = False
    except Exception as e:
        print(f"Erreur lors de l'ajout de compétence: {e}")
        success = False
    
    conn.close()
    return jsonify({'success': success})

@app.route('/api/competences/<competence_name>', methods=['DELETE'])
@login_required
def delete_competence(competence_name):
    user_id = get_current_user_id()
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM competences WHERE name=? AND user_id=?', 
                  (competence_name, user_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/competences/reset', methods=['POST'])
@login_required
def reset_competences():
    user_id = get_current_user_id()
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Supprimer toutes les compétences de l'utilisateur
    cursor.execute('DELETE FROM competences WHERE user_id = ?', (user_id,))
    
    # Réinsérer les compétences par défaut
    default_competences = [
        'monitoring', 'scripting', 'virtualisation', 'firewall', 'pentest', 
        'soc', 'incident-response', 'compliance', 'kubernetes', 'docker',
        'ansible', 'terraform', 'aws', 'azure', 'gcp', 'linux', 'windows',
        'python', 'powershell', 'bash', 'siem', 'forensic', 'malware-analysis'
    ]
    
    for comp in default_competences:
        cursor.execute('INSERT INTO competences (name, date_creation, user_id) VALUES (?, ?, ?)', 
                     (comp, datetime.now().isoformat(), user_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# API Statistiques
@app.route('/api/stats')
@login_required
def get_stats():
    user_id = get_current_user_id()
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT status, COUNT(*) FROM candidatures WHERE user_id = ? GROUP BY status', 
                  (user_id,))
    status_counts = dict(cursor.fetchall())
    
    cursor.execute('SELECT COUNT(*) FROM candidatures WHERE user_id = ?', (user_id,))
    total = cursor.fetchone()[0]
    
    # Calculer le taux de réponse
    responses = sum(count for status, count in status_counts.items() 
                   if status in ['entretien', 'refusee', 'acceptee'])
    taux_reponse = round((responses / total * 100)) if total > 0 else 0
    
    conn.close()
    
    return jsonify({
        'total': total,
        'envoyees': status_counts.get('envoyee', 0),
        'relancees': status_counts.get('relancee', 0),
        'entretiens': status_counts.get('entretien', 0),
        'refusees': status_counts.get('refusee', 0),
        'acceptees': status_counts.get('acceptee', 0),
        'tauxReponse': taux_reponse
    })

# Export/Import
@app.route('/api/export/csv')
@login_required
def export_csv():
    user_id = get_current_user_id()
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM candidatures WHERE user_id = ?', (user_id,))
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # En-têtes
    writer.writerow([
        'Entreprise', 'Poste', 'Statut', 'Date envoi', 'Lien offre',
        'Contact email', 'Contact téléphone', 'Compétences', 'Notes', 'Nombre relances'
    ])
    
    # Données
    for row in cursor.fetchall():
        competences = ', '.join(json.loads(row[8])) if row[8] else ''
        relances_count = len(json.loads(row[11])) if row[11] else 0
        
        writer.writerow([
            row[1],  # company
            row[2],  # position
            row[3],  # status
            row[4],  # date_envoi
            row[5] or '',  # lien_offre
            row[6] or '',  # contact_email
            row[7] or '',  # contact_phone
            competences,
            row[9] or '',  # notes
            relances_count
        ])
    
    conn.close()
    
    # Créer la réponse
    output.seek(0)
    response = send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f"candidatures_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )
    
    return response

@app.route('/api/import', methods=['POST'])
@login_required
def import_data():
    user_id = get_current_user_id()
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Aucun fichier fourni'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Aucun fichier sélectionné'})
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        count = 0
        
        if file.filename.endswith('.json'):
            data = json.loads(file.read().decode('utf-8'))
            for item in data:
                cursor.execute('''
                    INSERT INTO candidatures 
                    (company, position, status, date_envoi, lien_offre, contact_email, 
                     contact_phone, competences, notes, date_creation, relances, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item.get('company', ''),
                    item.get('position', ''),
                    item.get('status', 'envoyee'),
                    item.get('dateEnvoi'),
                    item.get('lienOffre'),
                    item.get('contactEmail'),
                    item.get('contactPhone'),
                    json.dumps(item.get('competences', [])),
                    item.get('notes'),
                    datetime.now().isoformat(),
                    json.dumps(item.get('relances', [])),
                    user_id
                ))
                count += 1
        
        elif file.filename.endswith('.csv'):
            content = file.read().decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(content))
            
            for row in csv_reader:
                competences = row.get('Compétences', '').split(', ') if row.get('Compétences') else []
                competences = [c.strip() for c in competences if c.strip()]
                
                cursor.execute('''
                    INSERT INTO candidatures 
                    (company, position, status, date_envoi, lien_offre, contact_email, 
                     contact_phone, competences, notes, date_creation, relances, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row.get('Entreprise', ''),
                    row.get('Poste', ''),
                    row.get('Statut', 'envoyee'),
                    row.get('Date envoi'),
                    row.get('Lien offre'),
                    row.get('Contact email'),
                    row.get('Contact téléphone'),
                    json.dumps(competences),
                    row.get('Notes'),
                    datetime.now().isoformat(),
                    json.dumps([]),
                    user_id
                ))
                count += 1
        
        conn.commit()
        conn.close()
        
        backup_database()
        
        return jsonify({'success': True, 'count': count})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    init_db()
    print("🚀 Serveur démarré avec authentification complète")
    print("📱 Interface responsive avec sécurité multi-utilisateurs")
    app.run(debug=True)