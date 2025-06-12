from flask import Flask, render_template, request, jsonify, redirect, url_for
import sqlite3
from datetime import datetime
import json

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('festa.db')
    c = conn.cursor()
    
    # Tabella prodotti
    c.execute('''CREATE TABLE IF NOT EXISTS prodotti (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    prezzo REAL NOT NULL,
                    attivo BOOLEAN DEFAULT 1
                )''')
    
    # Tabella ordini
    c.execute('''CREATE TABLE IF NOT EXISTS ordini (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prodotto TEXT NOT NULL,
                    quantita INTEGER NOT NULL,
                    prezzo_unitario REAL NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )''')
    
    # Inserisco alcuni prodotti di esempio se la tabella è vuota
    c.execute('SELECT COUNT(*) FROM prodotti')
    if c.fetchone()[0] == 0:
        prodotti_esempio = [
            ('Birra', 3.0),
            ('Vino Rosso', 4.5),
            ('Vino Bianco', 4.5),
            ('Cocktail', 6.0),
            ('Acqua', 1.0),
            ('Coca Cola', 2.5),
            ('Spritz', 5.0)
        ]
        c.executemany('INSERT INTO prodotti (nome, prezzo) VALUES (?, ?)', prodotti_esempio)
    
    conn.commit()
    conn.close()

@app.route('/')
def cassa():
    conn = sqlite3.connect('festa.db')
    c = conn.cursor()
    c.execute('SELECT * FROM prodotti WHERE attivo = 1 ORDER BY nome')
    prodotti = c.fetchall()
    conn.close()
    return render_template('cassa.html', prodotti=prodotti)

@app.route('/configurazione')
def configurazione():
    conn = sqlite3.connect('festa.db')
    c = conn.cursor()
    c.execute('SELECT * FROM prodotti ORDER BY nome')
    prodotti = c.fetchall()
    conn.close()
    return render_template('configurazione.html', prodotti=prodotti)

@app.route('/api/aggiungi_prodotto', methods=['POST'])
def aggiungi_prodotto():
    data = request.json
    nome = data.get('nome')
    prezzo = float(data.get('prezzo'))
    
    conn = sqlite3.connect('festa.db')
    c = conn.cursor()
    c.execute('INSERT INTO prodotti (nome, prezzo) VALUES (?, ?)', (nome, prezzo))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/modifica_prodotto', methods=['POST'])
def modifica_prodotto():
    data = request.json
    id_prodotto = data.get('id')
    nome = data.get('nome')
    prezzo = float(data.get('prezzo'))
    attivo = data.get('attivo', True)
    
    conn = sqlite3.connect('festa.db')
    c = conn.cursor()
    c.execute('UPDATE prodotti SET nome = ?, prezzo = ?, attivo = ? WHERE id = ?', 
              (nome, prezzo, attivo, id_prodotto))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/elimina_prodotto', methods=['POST'])
def elimina_prodotto():
    data = request.json
    id_prodotto = data.get('id')
    
    conn = sqlite3.connect('festa.db')
    c = conn.cursor()
    c.execute('DELETE FROM prodotti WHERE id = ?', (id_prodotto,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/conferma_ordine', methods=['POST'])
def conferma_ordine():
    data = request.json
    carrello = data.get('carrello', [])
    
    conn = sqlite3.connect('festa.db')
    c = conn.cursor()
    
    for item in carrello:
        c.execute('INSERT INTO ordini (prodotto, quantita, prezzo_unitario) VALUES (?, ?, ?)',
                  (item['nome'], item['quantita'], item['prezzo']))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)