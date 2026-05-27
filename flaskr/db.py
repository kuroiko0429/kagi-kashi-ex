import sqlite3
import click
from flask import current_app, g


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()


def init_db():
    db = get_db()

    # スキーマの実行
    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))

    # シードデータの挿入
    # 1. サークル (Clubs)
    clubs_data = [
        ("ボードゲームサークル", "401", "locked", "本日は17:00から活動予定です。", "#10b981", "K-401"),
        ("コンピュータ研究会", "402", "active", "", "#4f46e5", "K-402"),
        ("写真部", "102", "locked", "", "#ec4899", "K-102"),
        ("軽音楽部", "204", "temp_locked", "機材搬入のため15分ほど施錠します。すぐ戻ります！", "#8b5cf6", "K-204"),
        ("アニメーション研究会", "105", "locked", "", "#f97316", "K-105"),
    ]
    for name, room, status, msg, color, key_num in clubs_data:
        db.execute(
            "INSERT INTO clubs (name, room_number, status, message, icon_color, key_number) VALUES (?, ?, ?, ?, ?, ?)",
            (name, room, status, msg, color, key_num)
        )

    # 2. サークルメンバー (Members)
    # 各サークルIDは1から5
    # 退部ロック検証用に登録日時をシード値として設定（佐藤太陽は60日前[解除可]、鈴木美咲は5日前[ロック中]）
    members_data = [
        # ボードゲームサークル (ID: 1)
        ("S2023001", "佐藤 太陽", 1, "datetime('now', '-60 days', 'localtime')"),
        ("S2023002", "鈴木 美咲", 1, "datetime('now', '-5 days', 'localtime')"),
        # コンピュータ研究会 (ID: 2)
        ("S2023003", "高橋 蓮", 2, "datetime('now', '-45 days', 'localtime')"),
        ("S2023004", "田中 葵", 2, "datetime('now', '-10 days', 'localtime')"),
        # 写真部 (ID: 3)
        ("S2023005", "渡辺 陸", 3, "datetime('now', '-40 days', 'localtime')"),
        ("S2023006", "伊藤 結衣", 3, "datetime('now', '-12 days', 'localtime')"),
        # 軽音楽部 (ID: 4)
        ("S2023007", "中村 陽翔", 4, "datetime('now', '-50 days', 'localtime')"),
        ("S2023008", "小林 凛", 4, "datetime('now', '-2 days', 'localtime')"),
        # アニメーション研究会 (ID: 5)
        ("S2023009", "加藤 颯太", 5, "datetime('now', '-35 days', 'localtime')"),
        ("S2023010", "吉田 杏", 5, "datetime('now', '-8 days', 'localtime')"),
    ]
    for student_id, name, club_id, reg_expr in members_data:
        db.execute(
            f"INSERT INTO members (student_id, name, club_id, registered_at) VALUES (?, ?, ?, {reg_expr})",
            (student_id, name, club_id)
        )

    # 3. 貸出中のレコード設定 (コンピュータ研究会は現在活動中(active)なので貸出履歴を挿入)
    db.execute(
        "INSERT INTO borrow_records (club_id, student_id, student_name, key_number, borrowed_at) VALUES (?, ?, ?, ?, datetime('now', '-2 hours'))",
        (2, "S2023003", "高橋 蓮", "K-402")
    )
    
    # 4. 貸出中のレコード設定 (軽音楽部は現在一時施錠中(temp_locked)なので貸出履歴を挿入)
    db.execute(
        "INSERT INTO borrow_records (club_id, student_id, student_name, key_number, borrowed_at) VALUES (?, ?, ?, ?, datetime('now', '-4 hours'))",
        (4, "S2023007", "中村 陽翔", "K-204")
    )

    # 5. 活動報告書 (Activity Reports) の初期データ
    reports_data = [
        (1, "佐藤 太陽", "S2023001", "2026-05-20", "新入生歓迎ゲーム会を実施しました。カタンとカルカソンヌをプレイし、大いに盛り上がりました。"),
        (2, "高橋 蓮", "S2023003", "2026-05-22", "Webアプリ制作の勉強会を行いました。FlaskとTailwindを用いたモバイル画面設計について議論しました。"),
        (3, "渡辺 陸", "S2023005", "2026-05-18", "学内ポートレート撮影会を開催しました。構図とライティングについての基礎講座も行いました。"),
    ]
    for club_id, reporter_name, student_id, report_date, desc in reports_data:
        db.execute(
            "INSERT INTO activity_reports (club_id, reporter_name, student_id, report_date, description) VALUES (?, ?, ?, ?, ?)",
            (club_id, reporter_name, student_id, report_date, desc)
        )

    db.commit()


@click.command('init-db')
def init_db_command():
    """既存のデータをクリアし、新規テーブルを作成します。"""
    init_db()
    click.echo('データベースを初期化しました。初期シードデータを投入しました。')


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
