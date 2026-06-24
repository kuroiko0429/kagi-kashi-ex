import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from . import db


def create_app(test_config=None):
    # appの作成と設定
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite'),
    )

    # テスト中か
    if test_config is None:
        # 設定用ファイルがあればそれを読み込む
        app.config.from_pyfile('config.py', silent=True)
    else:
        # テスト中ならテスト用設定を読み込む
        app.config.from_mapping(test_config)

    # インスタンスフォルダの生成
    os.makedirs(app.instance_path, exist_ok=True)

    # データベースの初期化登録
    db.init_app(app)

    # コンテキストプロセッサー: 全ページで現在ログイン中のユーザー情報やセッションを利用可能にする
    @app.context_processor
    def inject_user():
        return {
            'current_user_id': session.get('user_id'),
            'current_user_name': session.get('user_name'),
        }

    # キャッシュ無効化設定
    @app.after_request
    def add_header(response):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response

    # ログインページ
    @app.route('/login', methods=('GET', 'POST'))
    def login():
        if request.method == 'POST':
            student_id = request.form['student_id'].strip().upper()
            name = request.form['name'].strip()

            if not student_id or not name:
                flash('学籍番号と氏名を入力してください。', 'error')
                return render_template('login.html')

            # セキュリティ：学籍番号がDBに存在するか確認（なりすまし防止）
            conn = db.get_db()
            member = conn.execute(
                'SELECT name FROM members WHERE student_id = ? LIMIT 1',
                (student_id,)
            ).fetchone()
            if not member:
                flash('この学籍番号はシステムに登録されていません。Googleアカウントでログインしてください。', 'error')
                return render_template('login.html')

            # DB登録氏名を使用（フォーム入力の氏名は無視してなりすまし防止）
            display_name = member['name']

            # セッションにユーザー情報を保存
            session['user_id'] = student_id
            session['user_name'] = display_name

            flash(f'{display_name}さん、ログインしました。', 'success')

            # 元のページに戻るか、一覧ページへリダイレクト（オープンリダイレクト防止）
            next_url = request.args.get('next', '')
            if next_url and (not next_url.startswith('/') or next_url.startswith('//')):
                next_url = ''
            return redirect(next_url or url_for('index'))

        return render_template('login.html')

    # Load .env manually if present
    def load_dotenv():
        import os
        if os.path.exists('.env'):
            try:
                with open('.env', encoding='utf-8') as f:
                    for line in f:
                        if line.strip() and not line.strip().startswith('#'):
                            parts = line.strip().split('=', 1)
                            if len(parts) == 2:
                                k = parts[0].strip()
                                v = parts[1].strip()
                                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                                    v = v[1:-1]
                                os.environ[k] = v
            except Exception:
                pass

    # Googleログイン転送
    @app.route('/google_login')
    def google_login():
        load_dotenv()
        import os
        next_url = request.args.get('next', '')
        
        client_id = os.environ.get('GOOGLE_CLIENT_ID')
        client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        mock_login = os.environ.get('GOOGLE_MOCK_LOGIN', 'false').lower() == 'true'
        
        if not client_id or not client_secret:
            if mock_login:
                return redirect(url_for('mock_google_signin', next=next_url))
            else:
                return render_template('google_setup_warning.html', next_url=next_url)
            
        # 実際の Google OAuth 2.0 認可リクエスト
        import urllib.parse
        redirect_uri = url_for('google_callback', _external=True)
        
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'state': next_url,
            'hd': 'do-johodai.ac.jp', # Google側でドメインを情報大に固定
            'prompt': 'select_account'
        }
        
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
        return redirect(auth_url)

    # Googleアカウント選択モック画面（開発・検証用）
    @app.route('/mock_google_signin')
    def mock_google_signin():
        load_dotenv()
        import os
        next_url = request.args.get('next', '')
        mock_login = os.environ.get('GOOGLE_MOCK_LOGIN', 'false').lower() == 'true'
        
        client_id = os.environ.get('GOOGLE_CLIENT_ID')
        client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        if not mock_login:
            return render_template('google_setup_warning.html', next_url=next_url)
            
        return render_template('mock_google_signin.html', next_url=next_url)

    # Googleログイン後のコールバック処理
    @app.route('/google_callback')
    def google_callback():
        load_dotenv()
        import os
        code = request.args.get('code')
        state = request.args.get('state', '') # next_url
        error = request.args.get('error')
        
        if error:
            flash(f'Googleログインエラー: {error}', 'error')
            return redirect(url_for('login', next=state))

        client_id = os.environ.get('GOOGLE_CLIENT_ID')
        client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        mock_login = os.environ.get('GOOGLE_MOCK_LOGIN', 'false').lower() == 'true'

        if not code:
            if mock_login:
                # モックログインの直接パラメータ取得（GOOGLE_MOCK_LOGIN=true の場合のみ）
                email = request.args.get('email', '').strip().lower()
                name = request.args.get('name', '').strip()
                next_url = request.args.get('next', '')
            else:
                flash('不正なリクエストです。認証コードが見つかりません。', 'error')
                return redirect(url_for('login', next=state))
        else:
            # 実際の Google OAuth コードとアクセストークンの交換
            import urllib.request
            import urllib.parse
            import json
            
            redirect_uri = url_for('google_callback', _external=True)
            
            token_url = "https://oauth2.googleapis.com/token"
            data = urllib.parse.urlencode({
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code'
            }).encode('utf-8')
            
            try:
                req = urllib.request.Request(token_url, data=data, headers={
                    'Content-Type': 'application/x-www-form-urlencoded'
                })
                with urllib.request.urlopen(req) as res:
                    token_data = json.loads(res.read().decode('utf-8'))
                    
                access_token = token_data.get('access_token')
                
                # アクセストークンを使ってユーザー情報を取得
                userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"
                req_user = urllib.request.Request(userinfo_url, headers={
                    'Authorization': f'Bearer {access_token}'
                })
                with urllib.request.urlopen(req_user) as res_user:
                    user_info = json.loads(res_user.read().decode('utf-8'))
                    
                email = user_info.get('email', '').strip().lower()
                name = user_info.get('name', '').strip()
                next_url = state
            except Exception as e:
                flash(f'Google認証情報の取得中にエラーが発生しました: {str(e)}', 'error')
                return redirect(url_for('login', next=state))

        # @do-johodai.ac.jp ドメイン制限チェック
        if not email.endswith('@do-johodai.ac.jp'):
            flash('北海道情報大学のGoogleアカウント（@do-johodai.ac.jp）のみ使用可能です。', 'error')
            return redirect(url_for('login', next=next_url))

        # 学籍番号をEメールから抽出（例: s2023001 -> S2023001）
        student_id = email.split('@')[0].upper()

        conn = db.get_db()
        member = conn.execute(
            'SELECT name FROM members WHERE student_id = ? LIMIT 1',
            (student_id,)
        ).fetchone()

        if member:
            display_name = member['name']
        else:
            display_name = name if name else "ゲスト学生"

        session['user_id'] = student_id
        session['user_name'] = display_name
        session['user_email'] = email
        session['is_google_login'] = True

        flash(f'Googleアカウント ({email}) でログインしました。', 'success')
        # オープンリダイレクト防止：相対パスのみ許可
        if next_url and (not next_url.startswith('/') or next_url.startswith('//')):
            next_url = ''
        return redirect(next_url or url_for('index'))

    # ログアウトページ
    @app.route('/logout')
    def logout():
        session.clear()
        flash('ログアウトしました。', 'success')
        return redirect(url_for('index'))

    # メイン一覧ページ（Figmaモック準拠）
    @app.route('/')
    def index():
        conn = db.get_db()
        user_id = session.get('user_id')

        # お気に入り情報を含めてサークル一覧を取得
        if user_id:
            clubs = conn.execute(
                '''
                SELECT c.*, 
                       (SELECT COUNT(*) FROM favorites f WHERE f.club_id = c.id AND f.student_id = ?) as is_favorite,
                       (SELECT student_name FROM borrow_records br WHERE br.club_id = c.id AND br.returned_at IS NULL LIMIT 1) as borrower_name
                FROM clubs c
                ''',
                (user_id,)
            ).fetchall()
        else:
            clubs = conn.execute(
                '''
                SELECT c.*, 
                       0 as is_favorite,
                       (SELECT student_name FROM borrow_records br WHERE br.club_id = c.id AND br.returned_at IS NULL LIMIT 1) as borrower_name
                FROM clubs c
                '''
            ).fetchall()

        # お気に入りのクラブが上に来るように並び替えてPythonリストに変換
        clubs_list = []
        for club in clubs:
            c_dict = dict(club)
            # 現在のログインユーザーがお気に入りに入れているかを真偽値にする
            c_dict['is_favorite'] = bool(c_dict['is_favorite'])
            clubs_list.append(c_dict)

        # お気に入り登録されているものを最上部にソート
        clubs_list.sort(key=lambda x: x['is_favorite'], reverse=True)

        return render_template('index.html', keys=clubs_list)

    # 詳細ページ
    @app.route('/club/<int:club_id>')
    def detail(club_id):
        conn = db.get_db()
        user_id = session.get('user_id')

        # サークル情報の取得
        if user_id:
            club = conn.execute(
                '''
                SELECT c.*, 
                       (SELECT COUNT(*) FROM favorites f WHERE f.club_id = c.id AND f.student_id = ?) as is_favorite
                FROM clubs c
                WHERE c.id = ?
                ''',
                (user_id, club_id)
            ).fetchone()
        else:
            club = conn.execute(
                'SELECT c.*, 0 as is_favorite FROM clubs c WHERE c.id = ?',
                (club_id,)
            ).fetchone()

        if club is None:
            flash('指定されたサークルが見つかりません。', 'error')
            return redirect(url_for('index'))

        # 現在の貸出情報を取得 (returned_at が NULL)
        borrow_info = conn.execute(
            'SELECT * FROM borrow_records WHERE club_id = ? AND returned_at IS NULL LIMIT 1',
            (club_id,)
        ).fetchone()

        # 活動報告書一覧の取得 (新しい順)
        reports = conn.execute(
            'SELECT * FROM activity_reports WHERE club_id = ? ORDER BY created_at DESC',
            (club_id,)
        ).fetchall()

        # 登録メンバー一覧の取得（引継ぎ用）
        members = conn.execute(
            '''
            SELECT * FROM members 
            WHERE club_id = ? 
            ORDER BY CASE role 
                       WHEN 'president' THEN 1 
                       WHEN 'vice_president' THEN 2 
                       ELSE 3 
                     END ASC, 
                     student_id ASC
            ''',
            (club_id,)
        ).fetchall()

        # ログインユーザーのこのサークルでの役職・入部日を取得
        user_role = None
        user_registered_at = None
        if user_id:
            user_member = conn.execute(
                'SELECT role, registered_at FROM members WHERE club_id = ? AND student_id = ?',
                (club_id, user_id)
            ).fetchone()
            if user_member:
                user_role = user_member['role']
                user_registered_at = user_member['registered_at']

        # 伝言板メッセージの取得 (新しい順)
        # 部員でなければ公開(is_private=0)のみ表示
        # 部員であっても入部前の非公開メッセージは表示しない（情報漏洩防止）
        if user_role is not None:
            messages = conn.execute(
                '''
                SELECT cm.*, m.role
                FROM club_messages cm
                LEFT JOIN members m ON cm.club_id = m.club_id AND cm.student_id = m.student_id
                WHERE cm.club_id = ?
                  AND (cm.is_private = 0 OR cm.created_at >= ?)
                ORDER BY cm.created_at DESC
                ''',
                (club_id, user_registered_at)
            ).fetchall()
        else:
            messages = conn.execute(
                '''
                SELECT cm.*, m.role
                FROM club_messages cm
                LEFT JOIN members m ON cm.club_id = m.club_id AND cm.student_id = m.student_id
                WHERE cm.club_id = ? AND cm.is_private = 0
                ORDER BY cm.created_at DESC
                ''',
                (club_id,)
            ).fetchall()

        club_dict = dict(club)
        club_dict['is_favorite'] = bool(club_dict['is_favorite'])

        # エクスポート可能な月一覧の生成（直近12ヶ月分）
        import datetime
        now = datetime.datetime.now()
        export_months = []
        year = now.year
        month = now.month
        for _ in range(12):
            export_months.append(f"{year:04d}-{month:02d}")
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        current_month = now.strftime("%Y-%m")

        return render_template(
            'detail.html',
            club=club_dict,
            borrow_info=borrow_info,
            reports=reports,
            members=members,
            user_role=user_role,
            messages=messages,
            export_months=export_months,
            current_month=current_month
        )

    # 鍵を借りる処理
    @app.route('/club/<int:club_id>/borrow', methods=('GET', 'POST'))
    def borrow_key(club_id):
        # セキュリティ：ログイン必須チェック
        user_id = session.get('user_id')
        if not user_id:
            flash('鍵を借りるにはログインが必要です。', 'error')
            return redirect(url_for('login', next=request.path))

        conn = db.get_db()
        
        if request.method == 'POST':
            student_id = request.form['student_id'].strip().upper()
            name = request.form['name'].strip()
            key_number = request.form['key_number'].strip()

            if not student_id or not name or not key_number:
                flash('すべての項目を入力してください。', 'error')
                return redirect(url_for('borrow_key', club_id=club_id))

            # セキュリティ：なりすまし防止（ログイン学籍番号とフォーム入力値の照合）
            if student_id != user_id:
                flash('ログイン中の学籍番号でのみ鍵を借用できます（なりすまし防止）。', 'error')
                return redirect(url_for('borrow_key', club_id=club_id))

            # そのサークルに登録されているメンバーか確認
            member = conn.execute(
                'SELECT * FROM members WHERE club_id = ? AND student_id = ?',
                (club_id, student_id)
            ).fetchone()

            if not member:
                flash(f'学籍番号 {student_id} はこのサークルに登録されていません。', 'error')
                return redirect(url_for('borrow_key', club_id=club_id))

            # 鍵が既に貸し出し中かチェック
            active_borrow = conn.execute(
                'SELECT * FROM borrow_records WHERE club_id = ? AND returned_at IS NULL',
                (club_id,)
            ).fetchone()

            if active_borrow:
                flash('鍵はすでに貸し出し中です。', 'error')
                return redirect(url_for('detail', club_id=club_id))

            # トランザクション処理
            try:
                # 貸出レコードの追加
                conn.execute(
                    '''
                    INSERT INTO borrow_records (club_id, student_id, student_name, key_number) 
                    VALUES (?, ?, ?, ?)
                    ''',
                    (club_id, student_id, name, key_number)
                )
                # サークルステータスを活動中（active）に更新
                conn.execute(
                    "UPDATE clubs SET status = 'active', message = '' WHERE id = ?",
                    (club_id,)
                )
                conn.commit()
                flash(f'{name}さんが鍵番号 {key_number} を借りました。活動開始です！', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'鍵の貸し出し処理中にエラーが発生しました: {str(e)}', 'error')

            return redirect(url_for('detail', club_id=club_id))

        # GETメソッドの場合
        club = conn.execute(
            'SELECT * FROM clubs WHERE id = ?',
            (club_id,)
        ).fetchone()

        if club is None:
            flash('指定されたサークルが見つかりません。', 'error')
            return redirect(url_for('index'))

        if club['status'] != 'locked':
            flash('鍵はすでに貸し出し中です。', 'error')
            return redirect(url_for('detail', club_id=club_id))

        club_dict = dict(club)
        return render_template('borrow.html', club=club_dict)

    # 鍵を返す処理
    @app.route('/club/<int:club_id>/return', methods=('GET', 'POST'))
    def return_key(club_id):
        # セキュリティ：ログイン必須チェック
        user_id = session.get('user_id')
        if not user_id:
            flash('鍵を返却するにはログインが必要です。', 'error')
            return redirect(url_for('login', next=request.path))

        conn = db.get_db()

        if request.method == 'POST':
            # セキュリティ：サークルメンバーであるか認証（部外者の返却操作をブロック）
            member = conn.execute(
                'SELECT * FROM members WHERE club_id = ? AND student_id = ?',
                (club_id, user_id)
            ).fetchone()

            if not member:
                flash('このサークルの登録メンバーのみが鍵を返却できます（不正操作防止）。', 'error')
                return redirect(url_for('detail', club_id=club_id))

            # 現在の貸出レコードを取得
            active_borrow = conn.execute(
                'SELECT * FROM borrow_records WHERE club_id = ? AND returned_at IS NULL LIMIT 1',
                (club_id,)
            ).fetchone()

            if not active_borrow:
                flash('貸出中の鍵が見つかりません。', 'error')
                return redirect(url_for('detail', club_id=club_id))

            # トランザクション処理
            try:
                # 返却日時の記録
                conn.execute(
                    "UPDATE borrow_records SET returned_at = datetime('now', 'localtime') WHERE id = ?",
                    (active_borrow['id'],)
                )
                # ステータスを保管中（locked）に戻す、メッセージをクリア
                conn.execute(
                    "UPDATE clubs SET status = 'locked', message = '' WHERE id = ?",
                    (club_id,)
                )
                conn.commit()
                flash(f'{active_borrow["student_name"]}さんが鍵を返却しました。状態を「保管中」に戻しました。', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'鍵の返却処理中にエラーが発生しました: {str(e)}', 'error')

            return redirect(url_for('detail', club_id=club_id))

        # GETメソッドの場合
        # セキュリティ：サークルメンバーであるか認証（部外者の返却画面アクセスをブロック）
        member = conn.execute(
            'SELECT * FROM members WHERE club_id = ? AND student_id = ?',
            (club_id, user_id)
        ).fetchone()

        if not member:
            flash('このサークルの登録メンバーのみが鍵を返却できます。', 'error')
            return redirect(url_for('detail', club_id=club_id))

        club = conn.execute(
            'SELECT * FROM clubs WHERE id = ?',
            (club_id,)
        ).fetchone()

        if club is None:
            flash('指定されたサークルが見つかりません。', 'error')
            return redirect(url_for('index'))

        active_borrow = conn.execute(
            'SELECT * FROM borrow_records WHERE club_id = ? AND returned_at IS NULL LIMIT 1',
            (club_id,)
        ).fetchone()

        if not active_borrow:
            flash('貸出中の鍵が見つかりません。', 'error')
            return redirect(url_for('detail', club_id=club_id))

        club_dict = dict(club)
        return render_template('return.html', club=club_dict, borrow_info=active_borrow)

    # 状況・メッセージの更新処理
    @app.route('/club/<int:club_id>/status', methods=('POST',))
    def update_status(club_id):
        # セキュリティ：ログイン必須チェック
        user_id = session.get('user_id')
        if not user_id:
            flash('状況を変更するにはログインが必要です。', 'error')
            return redirect(url_for('login', next=request.path))

        status = request.form.get('status')
        message = request.form.get('message', '').strip()

        if status not in ('active', 'temp_locked'):
            flash('無効なステータスです。', 'error')
            return redirect(url_for('detail', club_id=club_id))

        conn = db.get_db()

        # セキュリティ：サークルメンバーか確認
        member = conn.execute(
            'SELECT * FROM members WHERE club_id = ? AND student_id = ?',
            (club_id, user_id)
        ).fetchone()
        if not member:
            flash('このサークルの登録メンバーのみが状況を変更できます。', 'error')
            return redirect(url_for('detail', club_id=club_id))

        try:
            conn.execute(
                "UPDATE clubs SET status = ?, message = ? WHERE id = ?",
                (status, message, club_id)
            )
            conn.commit()
            
            status_jp = "活動中" if status == "active" else "一時施錠中"
            flash(f'状況を「{status_jp}」に更新しました。', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'状況更新中にエラーが発生しました: {str(e)}', 'error')

        return redirect(url_for('detail', club_id=club_id))

    # クイック状況更新API (一時施錠・活動再開)
    @app.route('/club/<int:club_id>/quick_status', methods=('POST',))
    def quick_status(club_id):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'status': 'error', 'message': '状況を変更するにはログインが必要です。'}), 401
            
        status = request.form.get('status')
        message = request.form.get('message', '').strip()

        if status not in ('active', 'temp_locked'):
            return jsonify({'status': 'error', 'message': '無効なステータスです。'}), 400

        conn = db.get_db()
        
        # 鍵が貸出中であるか（保管中の場合は状況を変更できない）
        club = conn.execute('SELECT * FROM clubs WHERE id = ?', (club_id,)).fetchone()
        if not club:
            return jsonify({'status': 'error', 'message': '指定されたサークルが見つかりません。'}), 404
            
        if club['status'] == 'locked':
            return jsonify({'status': 'error', 'message': '鍵が保管中のため、状況を変更できません。まず鍵を借りてください。'}), 400

        # 操作ユーザーが該当サークルの部員であるかどうかの検証 (セキュリティ)
        member = conn.execute(
            'SELECT * FROM members WHERE club_id = ? AND student_id = ?',
            (club_id, user_id)
        ).fetchone()
        if not member:
            return jsonify({'status': 'error', 'message': 'このサークルの登録メンバーのみが状況を変更できます。'}), 403

        try:
            conn.execute(
                "UPDATE clubs SET status = ?, message = ? WHERE id = ?",
                (status, message, club_id)
            )
            conn.commit()
            status_jp = "活動中" if status == "active" else "一時施錠中"
            return jsonify({'status': 'success', 'message': f'状況を「{status_jp}」に変更しました。'})
        except Exception as e:
            conn.rollback()
            return jsonify({'status': 'error', 'message': f'データベースエラーが発生しました: {str(e)}'}), 500

    # 活動報告書の提出処理
    @app.route('/club/<int:club_id>/report', methods=('POST',))
    def submit_report(club_id):
        # セキュリティ：ログイン必須チェック
        user_id = session.get('user_id')
        if not user_id:
            flash('活動報告書を提出するにはログインが必要です。', 'error')
            return redirect(url_for('login', next=request.path))

        # セキュリティ：student_id はセッションから取得（フォーム値による他人へのなりすまし防止）
        student_id = user_id
        report_date = request.form['report_date'].strip()
        description = request.form['description'].strip()

        if not report_date or not description:
            flash('すべての項目を入力してください。', 'error')
            return redirect(url_for('club_admin', club_id=club_id))

        conn = db.get_db()

        # サークルメンバーか確認し、DB登録氏名を取得
        member = conn.execute(
            'SELECT * FROM members WHERE club_id = ? AND student_id = ?',
            (club_id, student_id)
        ).fetchone()

        if not member:
            flash('このサークルに登録されていないため、報告書を提出できません。', 'error')
            return redirect(url_for('club_admin', club_id=club_id))

        # 権限チェック：部長・副部長のみ提出可
        if member['role'] not in ('president', 'vice_president'):
            flash('活動報告書の提出は部長・副部長のみ行えます。', 'error')
            return redirect(url_for('club_admin', club_id=club_id))

        reporter_name = member['name']

        try:
            conn.execute(
                '''
                INSERT INTO activity_reports (club_id, reporter_name, student_id, report_date, description)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (club_id, reporter_name, student_id, report_date, description)
            )
            conn.commit()
            flash('活動報告書を提出しました！', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'活動報告提出中にエラーが発生しました: {str(e)}', 'error')

        return redirect(url_for('club_admin', club_id=club_id))

    # 管理者画面（部長・副部長専用）
    @app.route('/club/<int:club_id>/admin')
    def club_admin(club_id):
        user_id = session.get('user_id')
        if not user_id:
            flash('管理者画面にアクセスするにはログインが必要です。', 'error')
            return redirect(url_for('login', next=request.path))

        conn = db.get_db()
        club = conn.execute('SELECT * FROM clubs WHERE id = ?', (club_id,)).fetchone()
        if not club:
            flash('指定されたサークルが見つかりません。', 'error')
            return redirect(url_for('index'))

        # 権限チェック：部長・副部長のみアクセス可
        leader = conn.execute(
            'SELECT role FROM members WHERE club_id = ? AND student_id = ? AND role IN ("president", "vice_president")',
            (club_id, user_id)
        ).fetchone()
        if not leader:
            flash('管理者画面は部長・副部長のみアクセスできます。', 'error')
            return redirect(url_for('detail', club_id=club_id))

        user_role = leader['role']

        reports = conn.execute(
            'SELECT * FROM activity_reports WHERE club_id = ? ORDER BY created_at DESC',
            (club_id,)
        ).fetchall()

        members = conn.execute(
            '''
            SELECT * FROM members WHERE club_id = ?
            ORDER BY CASE role
                       WHEN 'president' THEN 1
                       WHEN 'vice_president' THEN 2
                       ELSE 3
                     END ASC, student_id ASC
            ''',
            (club_id,)
        ).fetchall()

        import datetime
        now = datetime.datetime.now()
        export_months = []
        year, month = now.year, now.month
        for _ in range(12):
            export_months.append(f"{year:04d}-{month:02d}")
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        current_month = now.strftime("%Y-%m")

        return render_template(
            'admin.html',
            club=dict(club),
            user_role=user_role,
            reports=reports,
            members=members,
            export_months=export_months,
            current_month=current_month,
        )

    # 活動報告エクスポート処理（CSVダウンロード）
    @app.route('/club/<int:club_id>/export_report')
    def export_report(club_id):
        # セキュリティ：ログイン必須チェック
        user_id = session.get('user_id')
        if not user_id:
            flash('報告書をエクスポートするにはログインが必要です。', 'error')
            return redirect(url_for('login', next=request.path))

        conn = db.get_db()
        # サークルの存在確認
        club = conn.execute(
            'SELECT * FROM clubs WHERE id = ?', (club_id,)
        ).fetchone()
        if not club:
            flash('指定されたサークルが見つかりません。', 'error')
            return redirect(url_for('index'))

        # セキュリティ：当該サークルの部員のみエクスポート可（IDOR防止）
        member = conn.execute(
            'SELECT * FROM members WHERE club_id = ? AND student_id = ?',
            (club_id, user_id)
        ).fetchone()
        if not member:
            flash('このサークルの登録メンバーのみが報告書をエクスポートできます。', 'error')
            return redirect(url_for('detail', club_id=club_id))

        # 対象月（デフォルト：当月）
        import datetime
        current_month = datetime.datetime.now().strftime("%Y-%m")
        selected_month = request.args.get('month', current_month).strip()

        # 鍵貸出履歴の取得（対象月で返却済みのもの）
        borrows = conn.execute(
            '''
            SELECT id, student_id, student_name, key_number, borrowed_at, returned_at,
                   date(borrowed_at) as b_date
            FROM borrow_records
            WHERE club_id = ? AND strftime('%Y-%m', borrowed_at) = ? AND returned_at IS NOT NULL
            ORDER BY borrowed_at ASC
            ''',
            (club_id, selected_month)
        ).fetchall()

        # # 活動報告の取得（対象月）
        reports = conn.execute(
            '''
            SELECT id, reporter_name, student_id, report_date, description
            FROM activity_reports
            WHERE club_id = ? AND substr(report_date, 1, 7) = ?
            ORDER BY report_date ASC
            ''',
            (club_id, selected_month)
        ).fetchall()

        from collections import defaultdict
        
        # 鍵貸出履歴を日付ごとにグループ化
        borrows_by_date = defaultdict(list)
        for b in borrows:
            borrows_by_date[b['b_date']].append(b)

        # 活動報告を日付ごとにグループ化
        reports_by_date = defaultdict(list)
        for r in reports:
            reports_by_date[r['report_date']].append(r)

        # 全日付の結合
        all_dates = sorted(list(set(borrows_by_date.keys()) | set(reports_by_date.keys())))

        days_ja = ["月", "火", "水", "木", "金", "土", "日"]
        rows = []

        for d_str in all_dates:
            try:
                dt = datetime.datetime.strptime(d_str, "%Y-%m-%d")
                day_of_week = days_ja[dt.weekday()]
            except Exception:
                day_of_week = ""

            day_borrows = borrows_by_date[d_str]
            day_reports = reports_by_date[d_str]

            num_rows = max(len(day_borrows), len(day_reports), 1)
            for i in range(num_rows):
                b = day_borrows[i] if i < len(day_borrows) else None
                r = day_reports[i] if i < len(day_reports) else None

                start_time = ""
                end_time = ""
                duration = ""
                reporter = ""
                description = ""

                if b:
                    try:
                        b_dt = b['borrowed_at']
                        r_dt = b['returned_at']
                        if isinstance(b_dt, str):
                            # if it's stored/returned as a string
                            b_dt = datetime.datetime.strptime(b_dt, "%Y-%m-%d %H:%M:%S")
                        if isinstance(r_dt, str):
                            r_dt = datetime.datetime.strptime(r_dt, "%Y-%m-%d %H:%M:%S")
                        
                        start_time = b_dt.strftime("%H:%M")
                        end_time = r_dt.strftime("%H:%M")
                        diff = r_dt - b_dt
                        duration = f"{diff.total_seconds() / 3600:.1f}"
                    except Exception:
                        start_time = str(b['borrowed_at'])
                        end_time = str(b['returned_at'])
                    
                    reporter = b['student_name']

                if r:
                    if not reporter:
                        reporter = r['reporter_name']
                    description = r['description']

                rows.append([
                    d_str,
                    day_of_week,
                    start_time,
                    end_time,
                    duration,
                    reporter,
                    description
                ])

        import csv
        import io
        from flask import Response

        output = io.StringIO()
        # UTF-8 BOMを追加
        output.write('\ufeff')

        writer = csv.writer(output)
        writer.writerow(['日付', '曜日', '開始時間', '終了時間', '活動時間(時間)', '担当者', '活動内容'])
        
        for row in rows:
            writer.writerow(row)

        csv_data = output.getvalue()
        
        club_name = club['name']
        filename = f"activity_report_{club_name}_{selected_month}.csv"
        
        from urllib.parse import quote
        encoded_filename = quote(filename)

        response = Response(csv_data, mimetype='text/csv')
        response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_filename}"
        return response


    # お気に入りトグルAPI（非同期AJAX用）
    @app.route('/club/<int:club_id>/favorite', methods=('POST',))
    def toggle_favorite(club_id):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'お気に入りを登録するにはログインが必要です。'}), 401

        conn = db.get_db()
        # 存在確認
        fav = conn.execute(
            'SELECT * FROM favorites WHERE student_id = ? AND club_id = ?',
            (user_id, club_id)
        ).fetchone()

        try:
            if fav:
                conn.execute(
                    'DELETE FROM favorites WHERE student_id = ? AND club_id = ?',
                    (user_id, club_id)
                )
                conn.commit()
                return jsonify({'status': 'success', 'is_favorite': False, 'message': 'お気に入りを解除しました。'})
            else:
                conn.execute(
                    'INSERT INTO favorites (student_id, club_id) VALUES (?, ?)',
                    (user_id, club_id)
                )
                conn.commit()
                return jsonify({'status': 'success', 'is_favorite': True, 'message': 'お気に入りに登録しました！'})
        except Exception as e:
            conn.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 500

    # メンバー登録追加処理（引継ぎ設定用・権限チェック付き）
    @app.route('/club/<int:club_id>/add_member', methods=('POST',))
    def add_member(club_id):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'ログインが必要です。'}), 401

        student_id = request.form.get('student_id', '').strip().upper()
        name = request.form.get('name', '').strip()

        if not student_id or not name:
            return jsonify({'status': 'error', 'message': 'すべての項目を入力してください。'}), 400

        conn = db.get_db()

        # 権限チェック：ログインユーザーがこのサークルの部長または副部長か確認
        leader = conn.execute(
            'SELECT role FROM members WHERE club_id = ? AND student_id = ? AND role IN ("president", "vice_president")',
            (club_id, user_id)
        ).fetchone()

        if not leader:
            return jsonify({'status': 'error', 'message': 'メンバー管理権限がありません（部長または副部長のみ実行可能です）。'}), 403

        # すでに登録されているか確認
        exists = conn.execute(
            'SELECT * FROM members WHERE club_id = ? AND student_id = ?',
            (club_id, student_id)
        ).fetchone()

        if exists:
            return jsonify({'status': 'error', 'message': 'このメンバーはすでに登録されています。'}), 400

        try:
            conn.execute(
                'INSERT INTO members (club_id, student_id, name, role) VALUES (?, ?, ?, "member")',
                (club_id, student_id, name)
            )
            conn.commit()
            return jsonify({'status': 'success', 'message': f'{name}さんをサークルメンバーとして登録しました！'})
        except Exception as e:
            conn.rollback()
            return jsonify({'status': 'error', 'message': f'エラーが発生しました: {str(e)}'}), 500

    # メンバー登録解除処理（引継ぎ設定用・30日ロック ＆ 権限チェック付き）
    @app.route('/club/<int:club_id>/remove_member', methods=('POST',))
    def remove_member(club_id):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'ログインが必要です。'}), 401

        student_id = request.form.get('student_id', '').strip().upper()
        if not student_id:
            return jsonify({'status': 'error', 'message': '学籍番号が指定されていません。'}), 400

        conn = db.get_db()

        # 権限チェック：ログインユーザーがこのサークルの部長または副部長か確認
        leader = conn.execute(
            'SELECT role FROM members WHERE club_id = ? AND student_id = ? AND role IN ("president", "vice_president")',
            (club_id, user_id)
        ).fetchone()

        if not leader:
            return jsonify({'status': 'error', 'message': 'メンバー管理権限がありません（部長または副部長のみ実行可能です）。'}), 403
        
        # メンバー情報の取得
        member = conn.execute(
            'SELECT * FROM members WHERE club_id = ? AND student_id = ?',
            (club_id, student_id)
        ).fetchone()

        if not member:
            return jsonify({'status': 'error', 'message': '指定されたメンバーが見つかりません。'}), 404

        # セキュリティ：退部30日ロックチェック（盗難防止の監査ログ維持）
        from datetime import datetime
        reg_val = member['registered_at']
        if isinstance(reg_val, datetime):
            reg_date = reg_val
        else:
            try:
                reg_date = datetime.strptime(reg_val.split('.')[0], '%Y-%m-%d %H:%M:%S')
            except Exception:
                reg_date = datetime.now()

        days_passed = (datetime.now() - reg_date).days
        if days_passed < 30:
            remaining = 30 - days_passed
            reg_date_str = reg_date.strftime('%Y-%m-%d')
            return jsonify({
                'status': 'error', 
                'message': f'盗難防止および監査ログ維持のため、サークル登録から30日間はメンバー登録の解除ができません。（登録日: {reg_date_str}、あと {remaining} 日間）'
            }), 400

        try:
            conn.execute(
                'DELETE FROM members WHERE club_id = ? AND student_id = ?',
                (club_id, student_id)
            )
            conn.commit()
            return jsonify({'status': 'success', 'message': f'{member["name"]}さんのサークル登録を解除しました。'})
        except Exception as e:
            conn.rollback()
            return jsonify({'status': 'error', 'message': f'エラーが発生しました: {str(e)}'}), 500

    # メンバー役職変更処理
    @app.route('/club/<int:club_id>/change_role', methods=('POST',))
    def change_role(club_id):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'ログインが必要です。'}), 401

        student_id = request.form.get('student_id', '').strip().upper()
        new_role = request.form.get('role', '').strip()

        if not student_id or not new_role:
            return jsonify({'status': 'error', 'message': 'パラメータが不足しています。'}), 400

        if new_role not in ['president', 'vice_president', 'member']:
            return jsonify({'status': 'error', 'message': '無効な役職です。'}), 400

        conn = db.get_db()

        # 権限チェック：ログインユーザーがこのサークルの部長または副部長か確認
        leader = conn.execute(
            'SELECT role FROM members WHERE club_id = ? AND student_id = ? AND role IN ("president", "vice_president")',
            (club_id, user_id)
        ).fetchone()

        if not leader:
            return jsonify({'status': 'error', 'message': 'メンバー管理権限がありません（部長または副部長のみ実行可能です）。'}), 403

        # 変更対象メンバーの存在確認
        member = conn.execute(
            'SELECT * FROM members WHERE club_id = ? AND student_id = ?',
            (club_id, student_id)
        ).fetchone()

        if not member:
            return jsonify({'status': 'error', 'message': '指定されたメンバーが見つかりません。'}), 404

        # セキュリティ：部長への昇格は現部長のみ実行可能（副部長による自己昇格防止）
        if new_role == 'president' and leader['role'] != 'president':
            return jsonify({'status': 'error', 'message': '部長への役職変更は現在の部長のみが実行できます。'}), 403

        try:
            # もし新しい部長（president）を設定する場合、現在の部長の役職を一般部員（member）に変更する
            if new_role == 'president':
                conn.execute(
                    'UPDATE members SET role = "member" WHERE club_id = ? AND role = "president"',
                    (club_id,)
                )

            conn.execute(
                'UPDATE members SET role = ? WHERE club_id = ? AND student_id = ?',
                (new_role, club_id, student_id)
            )
            conn.commit()
            
            role_names = {'president': '部長', 'vice_president': '副部長', 'member': '一般部員'}
            return jsonify({'status': 'success', 'message': f'{member["name"]}さんの役職を「{role_names[new_role]}」に変更しました。'})
        except Exception as e:
            conn.rollback()
            return jsonify({'status': 'error', 'message': f'エラーが発生しました: {str(e)}'}), 500

    # ユーザー設定（プロフィール・お気に入り・サークル登録）画面の表示
    @app.route('/settings')
    def settings():
        user_id = session.get('user_id')
        if not user_id:
            flash('ユーザー設定画面にアクセスするにはログインが必要です。', 'error')
            return redirect(url_for('login', next=request.path))

        conn = db.get_db()
        
        # 全サークル情報の取得
        clubs = conn.execute('SELECT * FROM clubs ORDER BY id ASC').fetchall()
        
        # 自分がどのサークルに入っているかを取得
        my_memberships = conn.execute(
            'SELECT * FROM members WHERE student_id = ?',
            (user_id,)
        ).fetchall()
        
        membership_map = {m['club_id']: m for m in my_memberships}
        
        # お気に入りサークルを取得
        my_favorites = conn.execute(
            'SELECT f.club_id, c.name, c.room_number FROM favorites f JOIN clubs c ON f.club_id = c.id WHERE f.student_id = ?',
            (user_id,)
        ).fetchall()
        
        from datetime import datetime
        clubs_list = []
        for club in clubs:
            c_dict = dict(club)
            club_id = c_dict['id']
            
            if club_id in membership_map:
                c_dict['is_member'] = True
                mem = membership_map[club_id]
                reg_val = mem['registered_at']
                if isinstance(reg_val, datetime):
                    reg_date = reg_val
                else:
                    try:
                        reg_date = datetime.strptime(reg_val.split('.')[0], '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        reg_date = datetime.now()
                
                c_dict['registered_at'] = reg_date.strftime('%Y-%m-%d')
                days_passed = (datetime.now() - reg_date).days
                c_dict['days_passed'] = days_passed
                c_dict['locked'] = days_passed < 30
                c_dict['remaining_days'] = 30 - days_passed
            else:
                c_dict['is_member'] = False
                c_dict['locked'] = False
                c_dict['remaining_days'] = 0
                c_dict['registered_at'] = ""
                
            clubs_list.append(c_dict)

        return render_template('settings.html', clubs=clubs_list, favorites=my_favorites)

    # 従来のルート互換性のためのリダイレクト
    @app.route('/my_clubs')
    def my_clubs():
        return redirect(url_for('settings'))

    # ユーザー設定（所属サークル登録）の一括保存処理
    @app.route('/settings/save', methods=('POST',))
    @app.route('/my_clubs/save', methods=('POST',))
    def save_settings():
        user_id = session.get('user_id')
        user_name = session.get('user_name')
        if not user_id:
            flash('ユーザー設定を更新するにはログインが必要です。', 'error')
            return redirect(url_for('login'))

        # チェックされたサークルIDのリストを取得
        selected_club_ids = [int(cid) for cid in request.form.getlist('clubs')]
        
        conn = db.get_db()
        
        # 現在加入しているサークルを取得
        current_memberships = conn.execute(
            'SELECT * FROM members WHERE student_id = ?',
            (user_id,)
        ).fetchall()
        
        current_club_ids = [m['club_id'] for m in current_memberships]
        membership_map = {m['club_id']: m for m in current_memberships}

        # 差分検出と退部バリデーション（30日退部ロック）
        from datetime import datetime
        for club_id in current_club_ids:
            if club_id not in selected_club_ids:
                # 30日退部ロックの検証
                mem = membership_map[club_id]
                reg_val = mem['registered_at']
                if isinstance(reg_val, datetime):
                    reg_date = reg_val
                else:
                    try:
                        reg_date = datetime.strptime(reg_val.split('.')[0], '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        reg_date = datetime.now()
                
                days_passed = (datetime.now() - reg_date).days
                if days_passed < 30:
                    club_name = conn.execute('SELECT name FROM clubs WHERE id = ?', (club_id,)).fetchone()['name']
                    remaining = 30 - days_passed
                    flash(f'盗難防止および監査ログ維持のため、登録から30日間はサークル「{club_name}」の登録解除ができません。あと {remaining} 日間お待ちいただく必要があります。', 'error')
                    return redirect(url_for('settings'))

        # トランザクション保存処理
        try:
            # 加入処理
            for club_id in selected_club_ids:
                if club_id not in current_club_ids:
                    conn.execute(
                        'INSERT INTO members (club_id, student_id, name) VALUES (?, ?, ?)',
                        (club_id, user_id, user_name)
                    )
            
            # 脱退処理
            for club_id in current_club_ids:
                if club_id not in selected_club_ids:
                    conn.execute(
                        'DELETE FROM members WHERE student_id = ? AND club_id = ?',
                        (user_id, club_id)
                    )
            
            conn.commit()
            flash('所属サークル設定を更新しました！', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'設定保存中にエラーが発生しました: {str(e)}', 'error')

        return redirect(url_for('settings'))

    # 伝言板メッセージ投稿処理
    @app.route('/club/<int:club_id>/message', methods=('POST',))
    def post_message(club_id):
        user_id = session.get('user_id')
        user_name = session.get('user_name')
        if not user_id:
            flash('メッセージを投稿するにはログインが必要です。', 'error')
            return redirect(url_for('login', next=url_for('detail', club_id=club_id)))

        content = request.form.get('content', '').strip()
        is_private = 1 if request.form.get('is_private') in ('1', 'on') else 0

        if not content:
            flash('メッセージ内容を入力してください。', 'error')
            return redirect(url_for('detail', club_id=club_id))

        conn = db.get_db()
        
        # セキュリティ：操作ユーザーが該当サークルの部員であるか確認
        member = conn.execute(
            'SELECT * FROM members WHERE club_id = ? AND student_id = ?',
            (club_id, user_id)
        ).fetchone()

        if not member:
            flash('メッセージを投稿するには、このサークルのメンバーである必要があります。', 'error')
            return redirect(url_for('detail', club_id=club_id))

        try:
            conn.execute(
                'INSERT INTO club_messages (club_id, student_id, sender_name, content, is_private) VALUES (?, ?, ?, ?, ?)',
                (club_id, user_id, user_name, content, is_private)
            )
            conn.commit()
            flash('メッセージを投稿しました！', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'メッセージ投稿中にエラーが発生しました: {str(e)}', 'error')

        return redirect(url_for('detail', club_id=club_id))

    # 伝言板メッセージ削除処理
    @app.route('/club/<int:club_id>/delete_message/<int:message_id>', methods=('POST',))
    def delete_message(club_id, message_id):
        user_id = session.get('user_id')
        if not user_id:
            flash('メッセージを削除するにはログインが必要です。', 'error')
            return redirect(url_for('login', next=url_for('detail', club_id=club_id)))

        conn = db.get_db()
        
        # メッセージ情報の取得
        message = conn.execute(
            'SELECT * FROM club_messages WHERE id = ? AND club_id = ?',
            (message_id, club_id)
        ).fetchone()

        if not message:
            flash('削除対象のメッセージが見つかりません。', 'error')
            return redirect(url_for('detail', club_id=club_id))

        # 権限チェック: 投稿者本人か、または部長・副部長か
        is_authorized = message['student_id'] == user_id
        if not is_authorized:
            leader = conn.execute(
                'SELECT role FROM members WHERE club_id = ? AND student_id = ? AND role IN ("president", "vice_president")',
                (club_id, user_id)
            ).fetchone()
            if leader:
                is_authorized = True

        if not is_authorized:
            flash('メッセージを削除する権限がありません（投稿者本人または部長・副部長のみ削除可能です）。', 'error')
            return redirect(url_for('detail', club_id=club_id))

        try:
            conn.execute('DELETE FROM club_messages WHERE id = ?', (message_id,))
            conn.commit()
            flash('メッセージを削除しました。', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'メッセージ削除中にエラーが発生しました: {str(e)}', 'error')

        return redirect(url_for('detail', club_id=club_id))

    return app