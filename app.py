from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime
import shutil
import os

app = Flask(__name__)
app.secret_key = 'esport_secret_key'
DATABASE = 'Esport.db'
BACKUP_DATABASE = 'Esport.db.backup'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

@app.route('/')
def index():
    conn = get_db()
    cursor = conn.cursor()
    
    teams = cursor.execute('SELECT * FROM teams').fetchall()
    players = cursor.execute('''
        SELECT p.*, t.team_name, GROUP_CONCAT(g.gear_name, ', ') AS gear_names
        FROM players p
        LEFT JOIN teams t ON p.team_id = t.team_id
        LEFT JOIN gears g ON p.player_id = g.player_id
        GROUP BY p.player_id
    ''').fetchall()
    tournaments = cursor.execute('SELECT * FROM tournaments').fetchall()
    match_results = cursor.execute('''
        SELECT mr.*, t.tournament_name, tm.team_name
        FROM match_results mr
        LEFT JOIN tournaments t ON mr.tournament_id = t.tournament_id
        LEFT JOIN teams tm ON mr.team_id = tm.team_id
        ORDER BY mr.match_date DESC
    ''').fetchall()
    
    conn.close()
    return render_template('index.html', teams=teams, players=players, tournaments=tournaments, match_results=match_results)

@app.route('/clear_data', methods=['POST'])
def clear_data():
    # Create a backup before clearing
    if os.path.exists(DATABASE):
        shutil.copy(DATABASE, BACKUP_DATABASE)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM match_results')
    cursor.execute('DELETE FROM gears')
    cursor.execute('DELETE FROM players')
    cursor.execute('DELETE FROM tournaments')
    cursor.execute('DELETE FROM teams')
    conn.commit()
    conn.close()
    flash('All dashboard data has been removed.', 'success')
    return redirect(url_for('index'))

@app.route('/undo_clear', methods=['POST'])
def undo_clear():
    # Restore from backup
    if os.path.exists(BACKUP_DATABASE):
        shutil.copy(BACKUP_DATABASE, DATABASE)
        flash('Data has been restored.', 'success')
    else:
        flash('No backup available to restore.', 'danger')
    return redirect(url_for('index'))

@app.route('/delete_item', methods=['POST'])
def delete_item():
    item_type = request.form.get('item_type')
    item_id = request.form.get('item_id')

    if not item_type or not item_id:
        flash('Invalid delete request.', 'danger')
        return redirect(url_for('index'))

    # Backup before deleting so undo can restore the last removal.
    if os.path.exists(DATABASE):
        shutil.copy(DATABASE, BACKUP_DATABASE)

    conn = get_db()
    cursor = conn.cursor()
    try:
        item_id_int = int(item_id)
    except ValueError:
        flash('Invalid delete request.', 'danger')
        conn.close()
        return redirect(url_for('index'))

    if item_type == 'team':
        cursor.execute('DELETE FROM match_results WHERE team_id = ?', (item_id_int,))
        cursor.execute('UPDATE players SET team_id = NULL WHERE team_id = ?', (item_id_int,))
        cursor.execute('DELETE FROM teams WHERE team_id = ?', (item_id_int,))
    elif item_type == 'player':
        cursor.execute('DELETE FROM gears WHERE player_id = ?', (item_id_int,))
        cursor.execute('DELETE FROM players WHERE player_id = ?', (item_id_int,))
    elif item_type == 'tournament':
        cursor.execute('DELETE FROM match_results WHERE tournament_id = ?', (item_id_int,))
        cursor.execute('DELETE FROM tournaments WHERE tournament_id = ?', (item_id_int,))
    elif item_type == 'result':
        cursor.execute('DELETE FROM match_results WHERE result_id = ?', (item_id_int,))
    else:
        flash('Invalid delete request.', 'danger')
        conn.close()
        return redirect(url_for('index'))

    conn.commit()
    conn.close()
    flash(f'{item_type.title()} record has been removed. Use Undo to restore it.', 'success')
    return redirect(url_for('index'))

@app.route('/custom_data', methods=['POST'])
def custom_data():
    item_type = request.form.get('item_type')
    item_id = request.form.get('item_id')

    if not item_type or not item_id:
        flash('Invalid request.', 'danger')
        return redirect(url_for('index'))

    try:
        item_id_int = int(item_id)
    except ValueError:
        flash('Invalid request.', 'danger')
        return redirect(url_for('index'))

    conn = get_db()
    cursor = conn.cursor()
    row = None
    if item_type == 'team':
        row = cursor.execute('SELECT * FROM teams WHERE team_id = ?', (item_id_int,)).fetchone()
    elif item_type == 'player':
        row = cursor.execute('''
            SELECT p.*, t.team_name
            FROM players p
            LEFT JOIN teams t ON p.team_id = t.team_id
            WHERE p.player_id = ?
        ''', (item_id_int,)).fetchone()
    elif item_type == 'tournament':
        row = cursor.execute('SELECT * FROM tournaments WHERE tournament_id = ?', (item_id_int,)).fetchone()
    elif item_type == 'result':
        row = cursor.execute('''
            SELECT mr.*, t.tournament_name, tm.team_name
            FROM match_results mr
            LEFT JOIN tournaments t ON mr.tournament_id = t.tournament_id
            LEFT JOIN teams tm ON mr.team_id = tm.team_id
            WHERE mr.result_id = ?
        ''', (item_id_int,)).fetchone()
    else:
        flash('Invalid request.', 'danger')
        conn.close()
        return redirect(url_for('index'))

    teams = []
    tournaments = []
    if item_type in ('player', 'result'):
        teams = cursor.execute('SELECT team_id, team_name FROM teams').fetchall()
    if item_type == 'result':
        tournaments = cursor.execute('SELECT tournament_id, tournament_name FROM tournaments').fetchall()

    conn.close()
    if not row:
        flash('Record not found.', 'danger')
        return redirect(url_for('index'))

    return render_template('custom_data.html', item_type=item_type, row=row, teams=teams, tournaments=tournaments)

@app.route('/update_custom_data', methods=['POST'])
def update_custom_data():
    item_type = request.form.get('item_type')
    item_id = request.form.get('item_id')

    if not item_type or not item_id:
        flash('Invalid update request.', 'danger')
        return redirect(url_for('index'))

    try:
        item_id_int = int(item_id)
    except ValueError:
        flash('Invalid update request.', 'danger')
        return redirect(url_for('index'))

    conn = get_db()
    cursor = conn.cursor()

    if item_type == 'team':
        team_name = request.form.get('team_name')
        coach_name = request.form.get('coach_name')
        country = request.form.get('country')
        cursor.execute('UPDATE teams SET team_name = ?, coach_name = ?, country = ? WHERE team_id = ?',
                       (team_name, coach_name if coach_name else None, country, item_id_int))
    elif item_type == 'player':
        player_name = request.form.get('player_name')
        team_id = request.form.get('team_id')
        game_role = request.form.get('game_role')
        age = request.form.get('age')
        cursor.execute('UPDATE players SET player_name = ?, team_id = ?, game_role = ?, age = ? WHERE player_id = ?',
                       (player_name, int(team_id) if team_id else None, game_role if game_role else None, int(age) if age else None, item_id_int))
    elif item_type == 'tournament':
        tournament_name = request.form.get('tournament_name')
        location = request.form.get('location')
        prize_pool = request.form.get('prize_pool')
        cursor.execute('UPDATE tournaments SET tournament_name = ?, location = ?, prize_pool = ? WHERE tournament_id = ?',
                       (tournament_name, location if location else None, float(prize_pool) if prize_pool else None, item_id_int))
    elif item_type == 'result':
        tournament_id = request.form.get('tournament_id')
        team_id = request.form.get('team_id')
        match_date = request.form.get('match_date')
        result = request.form.get('result')
        cursor.execute('UPDATE match_results SET tournament_id = ?, team_id = ?, match_date = ?, result = ? WHERE result_id = ?',
                       (int(tournament_id) if tournament_id else None, int(team_id) if team_id else None, match_date, result, item_id_int))
    else:
        flash('Invalid update request.', 'danger')
        conn.close()
        return redirect(url_for('index'))

    conn.commit()
    conn.close()
    flash(f'{item_type.title()} record has been updated.', 'success')
    return redirect(url_for('index'))

# === Action Route สำหรับบันทึกข้อมูลจาก Form ===

@app.route('/add_team', methods=['POST'])
def add_team():
    team_name = request.form.get('team_name')
    coach_name = request.form.get('coach_name')
    country = request.form.get('country')
    
    if team_name:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO teams (team_name, coach_name, country) VALUES (?, ?, ?)",
                       (team_name, coach_name if coach_name else None, country))
        conn.commit()
        conn.close()
        flash(f"เพิ่มทีม '{team_name}' เรียบร้อยแล้ว!", "success")
    return redirect(url_for('index'))

@app.route('/add_player', methods=['POST'])
def add_player():
    player_name = request.form.get('player_name')
    team_id = request.form.get('team_id')
    game_role = request.form.get('game_role')
    age = request.form.get('age')
    
    if player_name:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO players (team_id, player_name, game_role, age) VALUES (?, ?, ?, ?)",
                       (int(team_id) if team_id else None, player_name, game_role, int(age)))
        conn.commit()
        conn.close()
        flash(f"เพิ่มผู้เล่น '{player_name}' เรียบร้อยแล้ว!", "success")
    return redirect(url_for('index'))

@app.route('/add_tournament', methods=['POST'])
def add_tournament():
    tournament_name = request.form.get('tournament_name')
    location = request.form.get('location')
    prize_pool = request.form.get('prize_pool')
    
    if tournament_name:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tournaments (tournament_name, location, prize_pool) VALUES (?, ?, ?)",
                       (tournament_name, location, float(prize_pool)))
        conn.commit()
        conn.close()
        flash(f"เพิ่มรายการแข่ง '{tournament_name}' เรียบร้อยแล้ว!", "success")
    return redirect(url_for('index'))

@app.route('/add_result', methods=['POST'])
def add_result():
    tournament_id = request.form.get('tournament_id')
    team_id = request.form.get('team_id')
    match_date = request.form.get('match_date')
    result = request.form.get('result')
    
    if not match_date:
        match_date = datetime.now().strftime('%Y-%m-%d')
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO match_results (tournament_id, team_id, match_date, result) VALUES (?, ?, ?, ?)",
                   (int(tournament_id), int(team_id), match_date, result))
    conn.commit()
    conn.close()
    flash("บันทึกผลการแข่งขันเรียบร้อยแล้ว!", "success")
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)