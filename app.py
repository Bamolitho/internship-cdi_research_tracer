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
app.secret_key = 'okay_2025-08'  

# Configuration
base_dir = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(base_dir, "instance", 'candidatures.db')
BACKUP_DIR = os.path.normpath(os.path.join(base_dir, "instance", 'backups'))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DATABASE}"
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{BACKUP_DIR}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

def init_db():
    """Initialise la base de données avec les tables nécessaires"""
    # Créer le dossier de sauvegarde s'il n'existe pas
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    # Vérifier si la base de données existe
    db_exists = os.path.exists(DATABASE)
    
    try:
        # Créer la connexion (crée le fichier DB s'il n'existe pas)
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Activer les clés étrangères
        cursor.execute('PRAGMA foreign_keys = ON')
                
        # Table utilisateurs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                date_creation TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_login TEXT
            )
        ''')
        
        # Table candidatures
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS candidatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                position TEXT NOT NULL,
                status TEXT DEFAULT 'envoyee' CHECK (status IN ('envoyee', 'relancee', 'entretien', 'refusee', 'acceptee')),
                date_envoi TEXT,
                lien_offre TEXT,
                contact_email TEXT,
                contact_phone TEXT,
                competences TEXT DEFAULT '[]',
                notes TEXT,
                date_creation TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                relances TEXT DEFAULT '[]',
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Table certifications
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS certifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                obtention TEXT,
                expiration TEXT,
                date_creation TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Table compétences
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS competences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                date_creation TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(name, user_id)
            )
        ''')
        
        # Créer des index pour améliorer les performances
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_candidatures_user ON candidatures(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_candidatures_status ON candidatures(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_certifications_user ON certifications(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_competences_user ON competences(user_id)')
        
        # Migration sécurisée pour les anciennes versions
        try:
            # Vérifier et ajouter user_id si nécessaire
            for table in ['candidatures', 'certifications', 'competences']:
                cursor.execute(f'PRAGMA table_info({table})')
                columns = [column[1] for column in cursor.fetchall()]
                if 'user_id' not in columns:
                    cursor.execute(f'ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES users(id)')
                    print(f"Colonne user_id ajoutée à la table {table}")
                    
        except sqlite3.Error as e:
            print(f"Avertissement lors de la migration : {e}")
        
        # Valider la structure de la base de données
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [table[0] for table in cursor.fetchall()]
        expected_tables = ['users', 'candidatures', 'certifications', 'competences']
        
        for table in expected_tables:
            if table in tables:
                print(f"Table '{table}' prête")
            else:
                print(f"Erreur: Table '{table}' manquante")
        
        conn.commit()
        conn.close()
        
        if not db_exists:
            print(f"Base de données créée avec succès : {DATABASE}")
        else:
            print(f"Base de données mise à jour : {DATABASE}")
            
        return True
        
    except sqlite3.Error as e:
        return False
    except Exception as e:
        return False

def check_database():
    """Vérifie que la base de données est accessible et contient les tables nécessaires"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Vérifier les tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [table[0] for table in cursor.fetchall()]
        expected_tables = ['users', 'candidatures', 'certifications', 'competences']
        
        missing_tables = [table for table in expected_tables if table not in tables]
        
        if missing_tables:
            conn.close()
            return False
        
        # Vérifier l'accès en écriture
        cursor.execute('CREATE TABLE IF NOT EXISTS test_table (id INTEGER)')
        cursor.execute('DROP TABLE test_table')
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        return False

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
        return jsonify({'success': False, 'error': 'Nom d\'utilisateur ou email déjà utilisé'})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'success': False, 'error': 'Erreur de base de données lors de la création du compte'})
    except Exception as e:
        conn.close()
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

# Routes pour la gestion des fichiers de template
@app.route('/api/export/json')
@login_required
def export_json():
    """Export des données en format JSON"""
    user_id = get_current_user_id()
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Récupérer toutes les données utilisateur
    cursor.execute('SELECT * FROM candidatures WHERE user_id = ?', (user_id,))
    candidatures_data = []
    
    for row in cursor.fetchall():
        candidature = {
            'company': row[1],
            'position': row[2],
            'status': row[3],
            'dateEnvoi': row[4],
            'lienOffre': row[5],
            'contactEmail': row[6],
            'contactPhone': row[7],
            'competences': json.loads(row[8]) if row[8] else [],
            'notes': row[9],
            'relances': json.loads(row[11]) if row[11] else []
        }
        candidatures_data.append(candidature)
    
    # Récupérer les certifications
    cursor.execute('SELECT * FROM certifications WHERE user_id = ?', (user_id,))
    certifications_data = []
    
    for row in cursor.fetchall():
        certification = {
            'name': row[1],
            'obtention': row[2],
            'expiration': row[3]
        }
        certifications_data.append(certification)
    
    # Récupérer les compétences
    cursor.execute('SELECT name FROM competences WHERE user_id = ?', (user_id,))
    competences_data = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    
    # Créer le fichier JSON
    export_data = {
        'candidatures': candidatures_data,
        'certifications': certifications_data,
        'competences': competences_data,
        'export_date': datetime.now().isoformat(),
        'version': '1.0'
    }
    
    # Créer la réponse
    json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
    response = send_file(
        io.BytesIO(json_str.encode('utf-8')),
        mimetype='application/json',
        as_attachment=True,
        download_name=f"candidatures_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    
    return response

# Route pour les templates d'import
@app.route('/api/template/csv')
def download_csv_template():
    """Télécharger un template CSV pour l'import"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # En-têtes du template
    writer.writerow([
        'Entreprise', 'Poste', 'Statut', 'Date envoi', 'Lien offre',
        'Contact email', 'Contact téléphone', 'Compétences', 'Notes'
    ])
    
    # Ligne d'exemple
    writer.writerow([
        'Exemple Entreprise',
        'Développeur Python',
        'envoyee',
        '2024-01-15',
        'https://exemple.com/offre',
        'rh@exemple.com',
        '0123456789',
        'python, django, postgresql',
        'Candidature très intéressante'
    ])
    
    output.seek(0)
    response = send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='template_candidatures.csv'
    )
    
    return response

# Routes pour la gestion du profil utilisateur
@app.route('/api/profile', methods=['GET'])
@login_required
def get_profile():
    """Récupérer les informations du profil utilisateur"""
    user_id = get_current_user_id()
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT username, email, date_creation, last_login FROM users WHERE id = ?', 
                  (user_id,))
    user_data = cursor.fetchone()
    
    if user_data:
        # Statistiques utilisateur
        cursor.execute('SELECT COUNT(*) FROM candidatures WHERE user_id = ?', (user_id,))
        total_candidatures = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM certifications WHERE user_id = ?', (user_id,))
        total_certifications = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM competences WHERE user_id = ?', (user_id,))
        total_competences = cursor.fetchone()[0]
        
        profile = {
            'username': user_data[0],
            'email': user_data[1],
            'dateCreation': user_data[2],
            'lastLogin': user_data[3],
            'stats': {
                'candidatures': total_candidatures,
                'certifications': total_certifications,
                'competences': total_competences
            }
        }
        
        conn.close()
        return jsonify(profile)
    
    conn.close()
    return jsonify({'error': 'Utilisateur non trouvé'}), 404

@app.route('/api/profile/update', methods=['PUT'])
@login_required
def update_profile():
    """Mettre à jour le profil utilisateur"""
    user_id = get_current_user_id()
    data = request.json
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    try:
        # Vérifier si l'email est déjà utilisé par un autre utilisateur
        if 'email' in data:
            cursor.execute('SELECT id FROM users WHERE email = ? AND id != ?', 
                          (data['email'], user_id))
            if cursor.fetchone():
                conn.close()
                return jsonify({'success': False, 'error': 'Email déjà utilisé par un autre compte'})
        
        # Mettre à jour les champs fournis
        update_fields = []
        values = []
        
        if 'email' in data:
            update_fields.append('email = ?')
            values.append(data['email'])
        
        if update_fields:
            values.append(user_id)
            query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()
        
        conn.close()
        return jsonify({'success': True})
        
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'success': False, 'error': 'Erreur lors de la mise à jour'})

@app.route('/api/profile/change-password', methods=['PUT'])
@login_required
def change_password():
    """Changer le mot de passe utilisateur"""
    user_id = get_current_user_id()
    data = request.json
    
    current_password = data.get('currentPassword')
    new_password = data.get('newPassword')
    
    if not current_password or not new_password:
        return jsonify({'success': False, 'error': 'Mots de passe requis'})
    
    if len(new_password) < 6:
        return jsonify({'success': False, 'error': 'Le nouveau mot de passe doit contenir au moins 6 caractères'})
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Vérifier le mot de passe actuel
    cursor.execute('SELECT password_hash FROM users WHERE id = ?', (user_id,))
    current_hash = cursor.fetchone()[0]
    
    if not check_password_hash(current_hash, current_password):
        conn.close()
        return jsonify({'success': False, 'error': 'Mot de passe actuel incorrect'})
    
    # Mettre à jour le mot de passe
    new_hash = generate_password_hash(new_password)
    cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', 
                  (new_hash, user_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# Routes pour la gestion des sauvegardes
@app.route('/api/backup/create', methods=['POST'])
@login_required
def create_backup():
    """Créer une sauvegarde manuelle"""
    try:
        backup_database()
        return jsonify({'success': True, 'message': 'Sauvegarde créée avec succès'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/backup/list', methods=['GET'])
@login_required
def list_backups():
    """Lister les sauvegardes disponibles"""
    try:
        if not os.path.exists(BACKUP_DIR):
            return jsonify([])
        
        backups = []
        for filename in os.listdir(BACKUP_DIR):
            if filename.startswith('backup_') and filename.endswith('.db'):
                filepath = os.path.join(BACKUP_DIR, filename)
                stat = os.stat(filepath)
                backups.append({
                    'filename': filename,
                    'size': stat.st_size,
                    'date': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        
        # Trier par date (plus récent en premier)
        backups.sort(key=lambda x: x['date'], reverse=True)
        return jsonify(backups)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route pour la recherche
@app.route('/api/candidatures/search', methods=['GET'])
@login_required
def search_candidatures():
    """Rechercher dans les candidatures"""
    user_id = get_current_user_id()
    query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '')
    
    if not query and not status_filter:
        return jsonify([])
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Construire la requête SQL
    sql = 'SELECT * FROM candidatures WHERE user_id = ?'
    params = [user_id]
    
    if query:
        sql += ' AND (company LIKE ? OR position LIKE ? OR notes LIKE ?)'
        search_term = f'%{query}%'
        params.extend([search_term, search_term, search_term])
    
    if status_filter:
        sql += ' AND status = ?'
        params.append(status_filter)
    
    sql += ' ORDER BY date_creation DESC'
    
    cursor.execute(sql, params)
    
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

# Route pour les statistiques avancées
@app.route('/api/stats/advanced')
@login_required
def get_advanced_stats():
    """Statistiques avancées"""
    user_id = get_current_user_id()
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Statistiques par mois
    cursor.execute('''
        SELECT strftime('%Y-%m', date_creation) as month, COUNT(*) 
        FROM candidatures 
        WHERE user_id = ? 
        GROUP BY month 
        ORDER BY month DESC 
        LIMIT 12
    ''', (user_id,))
    monthly_stats = dict(cursor.fetchall())
    
    # Entreprises les plus contactées
    cursor.execute('''
        SELECT company, COUNT(*) as count 
        FROM candidatures 
        WHERE user_id = ? 
        GROUP BY company 
        ORDER BY count DESC 
        LIMIT 10
    ''', (user_id,))
    top_companies = dict(cursor.fetchall())
    
    # Temps moyen de réponse (approximatif)
    cursor.execute('''
        SELECT AVG(julianday(date_creation) - julianday(date_envoi)) as avg_days
        FROM candidatures 
        WHERE user_id = ? AND date_envoi IS NOT NULL AND status IN ('entretien', 'refusee', 'acceptee')
    ''', (user_id,))
    avg_response_time = cursor.fetchone()[0] or 0
    
    # Compétences les plus demandées
    cursor.execute('SELECT competences FROM candidatures WHERE user_id = ?', (user_id,))
    all_competences = []
    for row in cursor.fetchall():
        if row[0]:
            comp_list = json.loads(row[0])
            all_competences.extend(comp_list)
    
    # Compter les occurrences
    competence_counts = {}
    for comp in all_competences:
        competence_counts[comp] = competence_counts.get(comp, 0) + 1
    
    # Top 10 des compétences
    top_competences = dict(sorted(competence_counts.items(), 
                                key=lambda x: x[1], reverse=True)[:10])
    
    conn.close()
    
    return jsonify({
        'monthlyStats': monthly_stats,
        'topCompanies': top_companies,
        'avgResponseTime': round(avg_response_time, 1),
        'topCompetences': top_competences
    })

# Gestion des erreurs
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Ressource non trouvée'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Erreur serveur interne'}), 500

@app.errorhandler(403)
def forbidden(error):
    return jsonify({'error': 'Accès non autorisé'}), 403

# Middleware pour les en-têtes de sécurité
@app.after_request
def after_request(response):
    """Ajouter des en-têtes de sécurité"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

if __name__ == '__main__':
    print("Démarrage de l'application de suivi des candidatures...")
    # Initialiser la base de données
    if init_db():        
        # Vérification supplémentaire
        if check_database():
            print("Vérification de la base de données réussie")
        else:
            print("Problème détecté lors de la vérification")
    else:
        exit(1)
    
    print("=" * 50)
    print("Accédez à l'application sur : http://127.0.0.1:5000")
    print("=" * 50)
    
    try:
        app.run(debug=True, host='127.0.0.1', port=5000)
    except KeyboardInterrupt:
        print("\nArrêt du serveur demandé par l'utilisateur")
    except Exception as e:
        print(f"\nErreur lors du démarrage du serveur : {e}")
        exit(1)
