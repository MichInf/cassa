# app.py
from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    conn = sqlite3.connect('festa.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = sqlite3.connect('festa.db')
    c = conn.cursor()
    
    # Tabella prodotti
    c.execute('''CREATE TABLE IF NOT EXISTS prodotti
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  nome TEXT NOT NULL,
                  prezzo REAL NOT NULL,
                  attivo BOOLEAN DEFAULT 1)''')
    
    # Tabella sessioni/eventi
    c.execute('''CREATE TABLE IF NOT EXISTS sessioni
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  nome TEXT NOT NULL,
                  data_inizio DATETIME DEFAULT CURRENT_TIMESTAMP,
                  data_fine DATETIME NULL,
                  attiva BOOLEAN DEFAULT 1,
                  note TEXT)''')
    
    # Tabella ordini con riferimento alla sessione
    c.execute('''CREATE TABLE IF NOT EXISTS ordini
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  sessione_id INTEGER,
                  prodotto TEXT NOT NULL,
                  quantita INTEGER NOT NULL,
                  prezzo_unitario REAL NOT NULL,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (sessione_id) REFERENCES sessioni (id))''')
    
    # Inserisci prodotti di esempio se la tabella è vuota
    c.execute('SELECT COUNT(*) FROM prodotti')
    if c.fetchone()[0] == 0:
        prodotti_esempio = [
            ('Birra', 3.0),
            ('Vino Rosso', 4.5),
            ('Vino Bianco', 4.5),
            ('Cocktail', 6.0),
            ('Acqua', 1.0),
            ('Coca Cola', 2.5),
            ('Spritz', 5.0),
            ('Panino', 8.0),
            ('Pizza', 12.0),
            ('Caffè', 1.5)
        ]
        c.executemany('INSERT INTO prodotti (nome, prezzo) VALUES (?, ?)', prodotti_esempio)
    
    conn.commit()
    conn.close()

# ==================== ROUTE PRINCIPALI ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/config')
def configurazione():
    return render_template('configurazione.html')

@app.route('/statistiche')
def statistiche():
    return render_template('statistiche.html')

# ==================== API PRODOTTI ====================

@app.route('/api/prodotti')
def get_prodotti():
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM prodotti WHERE attivo = 1 ORDER BY nome')
            prodotti = [dict(row) for row in c.fetchall()]
        return jsonify(prodotti)
    except Exception as e:
        logger.error(f"Errore recupero prodotti: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tutti_prodotti')
def get_tutti_prodotti():
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM prodotti ORDER BY nome')
            prodotti = [dict(row) for row in c.fetchall()]
        return jsonify(prodotti)
    except Exception as e:
        logger.error(f"Errore recupero tutti prodotti: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/aggiungi_prodotto', methods=['POST'])
def aggiungi_prodotto():
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'Dati mancanti'}), 400
        
        nome = data.get('nome', '').strip()
        prezzo_str = data.get('prezzo')
        
        if not nome:
            return jsonify({'success': False, 'message': 'Nome prodotto richiesto'}), 400
        
        try:
            prezzo = float(prezzo_str)
            if prezzo <= 0:
                return jsonify({'success': False, 'message': 'Il prezzo deve essere positivo'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Prezzo non valido'}), 400
        
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('INSERT INTO prodotti (nome, prezzo) VALUES (?, ?)', (nome, prezzo))
            conn.commit()
        
        logger.info(f"Prodotto aggiunto: {nome} - €{prezzo}")
        return jsonify({'success': True, 'message': 'Prodotto aggiunto con successo'})
    except Exception as e:
        logger.error(f"Errore aggiunta prodotto: {str(e)}")
        return jsonify({'success': False, 'message': f'Errore: {str(e)}'}), 500

@app.route('/api/modifica_prodotto/<int:id>', methods=['PUT'])
def modifica_prodotto(id):
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'Dati mancanti'}), 400
        
        nome = data.get('nome', '').strip()
        prezzo_str = data.get('prezzo')
        attivo = data.get('attivo', True)
        
        if not nome:
            return jsonify({'success': False, 'message': 'Nome prodotto richiesto'}), 400
        
        try:
            prezzo = float(prezzo_str)
            if prezzo <= 0:
                return jsonify({'success': False, 'message': 'Il prezzo deve essere positivo'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Prezzo non valido'}), 400
        
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('UPDATE prodotti SET nome = ?, prezzo = ?, attivo = ? WHERE id = ?',
                     (nome, prezzo, attivo, id))
            conn.commit()
        
        logger.info(f"Prodotto modificato: {nome} - €{prezzo}")
        return jsonify({'success': True, 'message': 'Prodotto modificato con successo'})
    except Exception as e:
        logger.error(f"Errore modifica prodotto: {str(e)}")
        return jsonify({'success': False, 'message': f'Errore: {str(e)}'}), 500

@app.route('/api/elimina_prodotto/<int:id>', methods=['DELETE'])
def elimina_prodotto(id):
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM prodotti WHERE id = ?', (id,))
            conn.commit()
        
        logger.info(f"Prodotto eliminato: ID {id}")
        return jsonify({'success': True, 'message': 'Prodotto eliminato con successo'})
    except Exception as e:
        logger.error(f"Errore eliminazione prodotto: {str(e)}")
        return jsonify({'success': False, 'message': f'Errore: {str(e)}'}), 500

# ==================== API SESSIONI ====================

@app.route('/api/sessioni')
def get_sessioni():
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM sessioni ORDER BY data_inizio DESC')
            sessioni = [dict(row) for row in c.fetchall()]
        return jsonify(sessioni)
    except Exception as e:
        logger.error(f"Errore recupero sessioni: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessione_attiva')
def get_sessione_attiva():
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM sessioni WHERE attiva = 1 LIMIT 1')
            sessione = c.fetchone()
            if sessione:
                return jsonify(dict(sessione))
            else:
                return jsonify(None)
    except Exception as e:
        logger.error(f"Errore recupero sessione attiva: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/crea_sessione', methods=['POST'])
def crea_sessione():
    try:
        data = request.json
        if not data or not data.get('nome'):
            return jsonify({'success': False, 'message': 'Nome sessione richiesto'}), 400
        
        nome = data.get('nome').strip()
        note = data.get('note', '').strip()
        
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Chiudi sessione attiva precedente
            c.execute('UPDATE sessioni SET attiva = 0, data_fine = CURRENT_TIMESTAMP WHERE attiva = 1')
            
            # Crea nuova sessione
            c.execute('INSERT INTO sessioni (nome, note) VALUES (?, ?)', (nome, note))
            sessione_id = c.lastrowid
            conn.commit()
        
        logger.info(f"Nuova sessione creata: {nome} (ID: {sessione_id})")
        return jsonify({'success': True, 'message': f'Sessione "{nome}" avviata con successo', 'sessione_id': sessione_id})
    except Exception as e:
        logger.error(f"Errore creazione sessione: {str(e)}")
        return jsonify({'success': False, 'message': f'Errore: {str(e)}'}), 500

@app.route('/api/chiudi_sessione', methods=['POST'])
def chiudi_sessione():
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('UPDATE sessioni SET attiva = 0, data_fine = CURRENT_TIMESTAMP WHERE attiva = 1')
            conn.commit()
        
        logger.info("Sessione chiusa")
        return jsonify({'success': True, 'message': 'Sessione chiusa con successo'})
    except Exception as e:
        logger.error(f"Errore chiusura sessione: {str(e)}")
        return jsonify({'success': False, 'message': f'Errore: {str(e)}'}), 500

@app.route('/api/elimina_sessione/<int:sessione_id>', methods=['DELETE'])
def elimina_sessione(sessione_id):
    try:
        data = request.json
        password = data.get('password', '') if data else ''
        
        # Verifica password
        if password != '0000':
            return jsonify({'success': False, 'message': 'Password non corretta'}), 401
        
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Verifica che la sessione esista
            c.execute('SELECT nome FROM sessioni WHERE id = ?', (sessione_id,))
            sessione = c.fetchone()
            if not sessione:
                return jsonify({'success': False, 'message': 'Sessione non trovata'}), 404
            
            nome_sessione = sessione[0]
            
            # Elimina prima tutti gli ordini collegati
            c.execute('DELETE FROM ordini WHERE sessione_id = ?', (sessione_id,))
            ordini_eliminati = c.rowcount
            
            # Poi elimina la sessione
            c.execute('DELETE FROM sessioni WHERE id = ?', (sessione_id,))
            
            conn.commit()
        
        logger.info(f"Sessione eliminata: {nome_sessione} (ID: {sessione_id}) con {ordini_eliminati} ordini")
        return jsonify({
            'success': True, 
            'message': f'Sessione "{nome_sessione}" e {ordini_eliminati} ordini eliminati con successo'
        })
    except Exception as e:
        logger.error(f"Errore eliminazione sessione: {str(e)}")
        return jsonify({'success': False, 'message': f'Errore: {str(e)}'}), 500
# ==================== API ORDINI ====================

@app.route('/api/conferma_ordine', methods=['POST'])
def conferma_ordine():
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'Dati mancanti'}), 400
        
        carrello = data.get('carrello', [])
        if not carrello:
            return jsonify({'success': False, 'message': 'Carrello vuoto'}), 400
        
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Verifica sessione attiva
            c.execute('SELECT id FROM sessioni WHERE attiva = 1 LIMIT 1')
            sessione = c.fetchone()
            if not sessione:
                return jsonify({'success': False, 'message': 'Nessuna sessione attiva. Avvia una sessione dalla configurazione.'}), 400
            
            sessione_id = sessione[0]
            totale = 0
            
            for item in carrello:
                if not all(k in item for k in ['nome', 'quantita', 'prezzo']):
                    return jsonify({'success': False, 'message': 'Dati carrello incompleti'}), 400
                
                c.execute('INSERT INTO ordini (sessione_id, prodotto, quantita, prezzo_unitario) VALUES (?, ?, ?, ?)',
                         (sessione_id, item['nome'], item['quantita'], item['prezzo']))
                totale += item['quantita'] * item['prezzo']
            conn.commit()
        
        logger.info(f"Ordine confermato per sessione {sessione_id}: {len(carrello)} articoli, totale €{totale:.2f}")
        return jsonify({'success': True, 'message': f'Ordine confermato! Totale: €{totale:.2f}'})
    except Exception as e:
        logger.error(f"Errore conferma ordine: {str(e)}")
        return jsonify({'success': False, 'message': f'Errore: {str(e)}'}), 500

# ==================== API STATISTICHE ====================

@app.route('/api/statistiche_vendite')
def get_statistiche_vendite():
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Statistiche generali (sessione attiva)
            c.execute('SELECT id FROM sessioni WHERE attiva = 1 LIMIT 1')
            sessione_attiva = c.fetchone()
            
            if sessione_attiva:
                sessione_id = sessione_attiva[0]
                
                c.execute('''
                    SELECT 
                        COUNT(*) as totale_ordini,
                        SUM(quantita * prezzo_unitario) as incasso_totale,
                        SUM(quantita) as prodotti_venduti,
                        AVG(quantita * prezzo_unitario) as scontrino_medio
                    FROM ordini WHERE sessione_id = ?
                ''', (sessione_id,))
                stats_generali = dict(c.fetchone())
                
                # Prodotti più venduti (sessione attiva)
                c.execute('''
                    SELECT 
                        prodotto,
                        SUM(quantita) as quantita_venduta,
                        SUM(quantita * prezzo_unitario) as incasso_prodotto,
                        COUNT(*) as numero_ordini
                    FROM ordini 
                    WHERE sessione_id = ?
                    GROUP BY prodotto 
                    ORDER BY quantita_venduta DESC 
                    LIMIT 10
                ''', (sessione_id,))
                prodotti_top = [dict(row) for row in c.fetchall()]
                
                # Vendite per ora (sessione attiva)
                c.execute('''
                    SELECT 
                        strftime('%H', timestamp) as ora,
                        COUNT(*) as ordini_ora,
                        SUM(quantita * prezzo_unitario) as incasso_ora
                    FROM ordini 
                    WHERE sessione_id = ?
                    GROUP BY strftime('%H', timestamp)
                    ORDER BY ora
                ''', (sessione_id,))
                vendite_orarie = [dict(row) for row in c.fetchall()]
                
            else:
                # Nessuna sessione attiva
                stats_generali = {
                    'totale_ordini': 0,
                    'incasso_totale': 0,
                    'prodotti_venduti': 0,
                    'scontrino_medio': 0
                }
                prodotti_top = []
                vendite_orarie = []
            
            return jsonify({
                'statistiche_generali': stats_generali,
                'prodotti_top': prodotti_top,
                'vendite_orarie': vendite_orarie,
                'sessione_attiva': sessione_attiva is not None
            })
            
    except Exception as e:
        logger.error(f"Errore statistiche: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/statistiche_sessione/<int:sessione_id>')
def get_statistiche_sessione(sessione_id):
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Info sessione
            c.execute('SELECT * FROM sessioni WHERE id = ?', (sessione_id,))
            sessione_row = c.fetchone()
            if not sessione_row:
                return jsonify({'error': 'Sessione non trovata'}), 404
            
            sessione = dict(sessione_row)
            
            # Statistiche generali per la sessione
            c.execute('''
                SELECT 
                    COUNT(*) as totale_ordini,
                    SUM(quantita * prezzo_unitario) as incasso_totale,
                    SUM(quantita) as prodotti_venduti,
                    AVG(quantita * prezzo_unitario) as scontrino_medio
                FROM ordini WHERE sessione_id = ?
            ''', (sessione_id,))
            stats_generali = dict(c.fetchone())
            
            # Prodotti più venduti nella sessione
            c.execute('''
                SELECT 
                    prodotto,
                    SUM(quantita) as quantita_venduta,
                    SUM(quantita * prezzo_unitario) as incasso_prodotto,
                    COUNT(*) as numero_ordini
                FROM ordini 
                WHERE sessione_id = ?
                GROUP BY prodotto 
                ORDER BY quantita_venduta DESC 
                LIMIT 10
            ''', (sessione_id,))
            prodotti_top = [dict(row) for row in c.fetchall()]
            
            # Vendite per ora nella sessione
            c.execute('''
                SELECT 
                    strftime('%H', timestamp) as ora,
                    COUNT(*) as ordini_ora,
                    SUM(quantita * prezzo_unitario) as incasso_ora
                FROM ordini 
                WHERE sessione_id = ?
                GROUP BY strftime('%H', timestamp)
                ORDER BY ora
            ''', (sessione_id,))
            vendite_orarie = [dict(row) for row in c.fetchall()]
            
            return jsonify({
                'sessione': sessione,
                'statistiche_generali': stats_generali,
                'prodotti_top': prodotti_top,
                'vendite_orarie': vendite_orarie
            })
            
    except Exception as e:
        logger.error(f"Errore statistiche sessione: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/lista_sessioni_statistiche')
def get_lista_sessioni_statistiche():
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''
                SELECT 
                    s.*,
                    COUNT(o.id) as totale_ordini,
                    COALESCE(SUM(o.quantita * o.prezzo_unitario), 0) as incasso_totale
                FROM sessioni s
                LEFT JOIN ordini o ON s.id = o.sessione_id
                GROUP BY s.id
                ORDER BY s.data_inizio DESC
            ''')
            sessioni = [dict(row) for row in c.fetchall()]
        return jsonify(sessioni)
    except Exception as e:
        logger.error(f"Errore lista sessioni: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ==================== GESTIONE ERRORI ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint non trovato'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Errore interno del server'}), 500

# ==================== AVVIO APPLICAZIONE ====================

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5001, debug=True)