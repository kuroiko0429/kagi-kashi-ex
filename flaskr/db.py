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

        # テーブルが存在しない場合は自動的に初期化する
        cursor = g.db.cursor()
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clubs'")
            if not cursor.fetchone():
                init_db()
        except sqlite3.Error:
            pass

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
        # 元のテスト用クラブを実在するものにマッピング (ID 1-5)
        ("囲碁・将棋・ボードゲーム部", "401", "locked", "本日は17:00から活動予定です。", "#10b981", "K-401", "cultural"),
        ("Computer Operating Club(COC)", "402", "active", "", "#4f46e5", "K-402", "cultural"),
        ("写真サークル", "102", "locked", "", "#ec4899", "K-102", "association"),
        ("軽音楽部", "204", "temp_locked", "機材搬入のため15分ほど施錠します。すぐ戻ります！", "#8b5cf6", "K-204", "cultural"),
        ("総合創作サークル(SSS)", "105", "locked", "", "#f97316", "K-105", "cultural"),
        
        # 体育系クラブ
        ("バスケットボール部", "111", "locked", "", "#f97316", "K-111", "sports"),
        ("硬式野球部", "112", "locked", "", "#3b82f6", "K-112", "sports"),
        ("バドミントン部", "113", "locked", "", "#10b981", "K-113", "sports"),
        ("卓球部", "114", "locked", "", "#ef4444", "K-114", "sports"),
        ("軟式野球部", "115", "locked", "", "#6366f1", "K-115", "sports"),
        ("フットサル部", "116", "locked", "", "#8b5cf6", "K-116", "sports"),
        ("情報大ダーツサークル ～formura～", "117", "locked", "", "#ec4899", "K-117", "sports"),
        ("ミニバレーサークル", "118", "locked", "", "#f59e0b", "K-118", "sports"),
        ("バレーボール部", "119", "locked", "", "#14b8a6", "K-119", "sports"),

        # 文化系クラブ (COC、軽音楽部、ボードゲーム部、SSS はID 1-5で定義済み)
        ("アートクラブ", "211", "locked", "", "#f43f5e", "K-211", "cultural"),
        ("映像研究部", "212", "locked", "", "#06b6d4", "K-212", "cultural"),
        ("DTMサークル Sound Terminal", "213", "locked", "", "#84cc16", "K-213", "cultural"),
        ("eスポーツサークル", "214", "locked", "", "#a855f7", "K-214", "cultural"),
        ("宇宙開発研究会", "215", "locked", "", "#1e1b4b", "K-215", "cultural"),

        # 同好会 (写真サークルはID 3で定義済み)
        ("Yosakoiソーランサークル", "311", "locked", "", "#e11d48", "K-311", "association"),
        ("ESS(English Speaking Society)", "312", "locked", "", "#2563eb", "K-312", "association"),
        ("TRPG同好会", "313", "locked", "", "#16a34a", "K-313", "association"),
        ("ミリタリー同好会", "314", "locked", "", "#4b5563", "K-314", "association"),
        ("アコースティックギター同好会", "315", "locked", "", "#ca8a04", "K-315", "association"),
        ("ポケモンサークル「グラシデア」", "316", "locked", "", "#ea580c", "K-316", "association"),
        ("3DCG同好会", "317", "locked", "", "#9333ea", "K-317", "association"),
        ("ボランティアサークル", "318", "locked", "", "#059669", "K-318", "association"),
        ("謎解きサークル Mystery", "319", "locked", "", "#db2777", "K-319", "association"),
        ("吹奏楽サークル", "320", "locked", "", "#4f46e5", "K-320", "association"),
        ("硬式テニス部", "321", "locked", "", "#2563eb", "K-321", "association"),
        ("ソフトボール同好会", "322", "locked", "", "#0d9488", "K-322", "association"),
        ("ソフトテニスサークル", "323", "locked", "", "#0284c7", "K-323", "association"),
        ("バトルホビー同好会", "324", "locked", "", "#7c3aed", "K-324", "association"),
        ("競技麻雀同好会　てんほー", "325", "locked", "", "#b91c1c", "K-325", "association"),
        ("HIPHOP 同好会", "326", "locked", "", "#4f46e5", "K-326", "association"),
        ("ローカルゲーム同好会", "327", "locked", "", "#0891b2", "K-327", "association"),
        ("コスプレ同好会", "328", "locked", "", "#c026d3", "K-328", "association"),
        ("ゲーム開発同好会", "329", "locked", "", "#4f46e5", "K-329", "association"),
        ("演劇同好会", "330", "locked", "", "#ea580c", "K-330", "association"),
        ("ダンスサークル", "331", "locked", "", "#e11d48", "K-331", "association")
    ]
    for name, room, status, msg, color, key_num, cat in clubs_data:
        db.execute(
            "INSERT INTO clubs (name, room_number, status, message, icon_color, key_number, category) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, room, status, msg, color, key_num, cat)
        )

    # 2. サークルメンバー (Members)
    # 各サークルIDは1から5
    # 退部ロック検証用に登録日時をシード値として設定（佐藤太陽は60日前[解除可]、鈴木美咲は5日前[ロック中]）
    members_data = [
        # ボードゲームサークル (ID: 1)
        ("S2023001", "佐藤 太陽", 1, "president", "datetime('now', '-60 days', 'localtime')"),
        ("S2023002", "鈴木 美咲", 1, "vice_president", "datetime('now', '-5 days', 'localtime')"),
        # コンピュータ研究会 (ID: 2)
        ("S2023003", "高橋 蓮", 2, "president", "datetime('now', '-45 days', 'localtime')"),
        ("S2023004", "田中 葵", 2, "vice_president", "datetime('now', '-10 days', 'localtime')"),
        # 写真部 (ID: 3)
        ("S2023005", "渡辺 陸", 3, "president", "datetime('now', '-40 days', 'localtime')"),
        ("S2023006", "伊藤 結衣", 3, "vice_president", "datetime('now', '-12 days', 'localtime')"),
        # 軽音楽部 (ID: 4)
        ("S2023007", "中村 陽翔", 4, "president", "datetime('now', '-50 days', 'localtime')"),
        ("S2023008", "小林 凛", 4, "vice_president", "datetime('now', '-2 days', 'localtime')"),
        # アニメーション研究会 (ID: 5)
        ("S2023009", "加藤 颯太", 5, "president", "datetime('now', '-35 days', 'localtime')"),
        ("S2023010", "吉田 杏", 5, "vice_president", "datetime('now', '-8 days', 'localtime')"),
    ]
    for student_id, name, club_id, role, reg_expr in members_data:
        db.execute(
            f"INSERT INTO members (student_id, name, club_id, role, registered_at) VALUES (?, ?, ?, ?, {reg_expr})",
            (student_id, name, club_id, role)
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

    # 6. 伝言板メッセージ (Club Messages) の初期データ
    messages_data = [
        (1, "S2023001", "佐藤 太陽", "部室のホワイトボードの横に傘を忘れました。見つけた方は教えてください！"),
        (1, "S2023002", "鈴木 美咲", "了解です！今度部室に行ったときに確認してみますね。"),
        (2, "S2023003", "高橋 蓮", "部室のルーターの設定を変更しました。SSIDとパスワードは引き継ぎ用の資料に記載してあります。")
    ]
    for club_id, student_id, sender_name, content in messages_data:
        db.execute(
            "INSERT INTO club_messages (club_id, student_id, sender_name, content) VALUES (?, ?, ?, ?)",
            (club_id, student_id, sender_name, content)
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
