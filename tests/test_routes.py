import unittest
import os
import tempfile
from flaskr import create_app
from flaskr.db import init_db


class KagiKashiTestCase(unittest.TestCase):
    def setUp(self):
        # 一時ファイルにデータベースを作成
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app({
            'TESTING': True,
            'DATABASE': self.db_path,
            'SECRET_KEY': 'test_dev',
        })
        self.client = self.app.test_client()

        # データベースの初期化
        with self.app.app_context():
            init_db()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_index_route(self):
        """一覧画面が正常にロードされるかテスト"""
        rv = self.client.get('/')
        self.assertEqual(rv.status_code, 200)
        html = rv.data.decode('utf-8')
        self.assertIn("活動状況", html)
        self.assertIn("囲碁・将棋・ボードゲーム部", html)

    def test_login_logout(self):
        """ログイン・ログアウト処理が正常に動作するかテスト"""
        # GET
        rv = self.client.get('/login')
        self.assertEqual(rv.status_code, 200)
        html = rv.data.decode('utf-8')
        self.assertIn("ログインする", html)

        # POST Login
        rv = self.client.post('/login', data=dict(
            student_id='S2023001',
            name='佐藤 太陽'
        ), follow_redirects=True)
        self.assertEqual(rv.status_code, 200)
        html = rv.data.decode('utf-8')
        self.assertIn("佐藤 太陽", html)

        # Logout
        rv = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(rv.status_code, 200)
        html = rv.data.decode('utf-8')
        self.assertIn("ログアウトしました", html)

    def test_club_detail(self):
        """詳細画面が正常にロードされるかテスト"""
        # 囲碁・将棋・ボードゲーム部 (ID: 1)
        rv = self.client.get('/club/1')
        self.assertEqual(rv.status_code, 200)
        html = rv.data.decode('utf-8')
        self.assertIn("囲碁・将棋・ボードゲーム部", html)
        self.assertIn("部屋番号: 401", html)

    def test_borrow_and_return_key(self):
        """鍵の借り出しと返却フローをテスト"""
        # 1. 囲碁・将棋・ボードゲーム部(ID:1)のメンバー「佐藤 太陽 (S2023001)」で借りる
        # セキュリティ：借用にはログインが必要
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023001'
            sess['user_name'] = '佐藤 太陽'

        rv = self.client.post('/club/1/borrow', data=dict(
            student_id='S2023001',
            name='佐藤 太陽',
            key_number='K-401'
        ), follow_redirects=True)
        self.assertEqual(rv.status_code, 200)
        html = rv.data.decode('utf-8')
        # 借用中メッセージや返却ボタンが出現するか確認
        self.assertIn("現在の借用状況", html)
        self.assertIn("佐藤 太陽", html)

        # 2. 登録メンバー外の学籍番号で借りようとすると弾かれるかテスト
        # コンピュータ研究会(ID:2)に、ボードゲームのメンバー(S2023001)が借りようとする
        rv = self.client.post('/club/2/borrow', data=dict(
            student_id='S2023001', # 登録外の学籍番号
            name='佐藤 太陽',
            key_number='K-402'
        ), follow_redirects=True)
        self.assertEqual(rv.status_code, 200)
        html = rv.data.decode('utf-8')
        self.assertIn("登録されていません", html)

        # 3. 鍵を返却する
        # 現在ログイン中の S2023001 はボードゲームのメンバーなので返却可能
        rv = self.client.post('/club/1/return', follow_redirects=True)
        self.assertEqual(rv.status_code, 200)
        html = rv.data.decode('utf-8')
        self.assertIn("保管中", html)

    def test_status_update(self):
        """状況変更をテスト"""
        # コンピュータ研究会 (ID:2) は初期状態で active
        # 一時施錠中に変更
        rv = self.client.post('/club/2/status', data=dict(
            status='temp_locked',
            message='お昼休みのため30分施錠します'
        ), follow_redirects=True)
        self.assertEqual(rv.status_code, 200)
        html = rv.data.decode('utf-8')
        self.assertIn("一時施錠中", html)
        self.assertIn("お昼休み", html)

    def test_activity_report(self):
        """活動報告提出をテスト"""
        # 囲碁・将棋・ボードゲーム部(ID:1)のメンバー「佐藤 太陽 (S2023001)」で提出
        rv = self.client.post('/club/1/report', data=dict(
            student_id='S2023001',
            reporter_name='佐藤 太陽',
            report_date='2026-05-27',
            description='みんなで楽しくボードゲーム会をしました！'
        ), follow_redirects=True)
        self.assertEqual(rv.status_code, 200)
        html = rv.data.decode('utf-8')
        self.assertIn("みんなで楽しく", html)

    def test_favorite_toggle(self):
        """お気に入りトグルをテスト"""
        # 未ログイン時は401エラー
        rv = self.client.post('/club/1/favorite')
        self.assertEqual(rv.status_code, 401)

        # ログインする
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023001'
            sess['user_name'] = '佐藤 太陽'

        # お気に入り登録
        rv = self.client.post('/club/1/favorite')
        self.assertEqual(rv.status_code, 200)
        json_data = rv.get_json()
        self.assertEqual(json_data['status'], 'success')
        self.assertEqual(json_data['is_favorite'], True)

        # お気に入り解除
        rv = self.client.post('/club/1/favorite')
        self.assertEqual(rv.status_code, 200)
        json_data = rv.get_json()
        self.assertEqual(json_data['is_favorite'], False)

    def test_borrow_get_page(self):
        """鍵借用専用画面の表示テスト"""
        # セキュリティ：ログインが必要
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023001'
            sess['user_name'] = '佐藤 太陽'

        # 囲碁・将棋・ボードゲーム部 (ID: 1) は初期状態で locked (保管中)
        rv = self.client.get('/club/1/borrow')
        self.assertEqual(rv.status_code, 200)
        html = rv.data.decode('utf-8')
        self.assertIn("鍵を借りる", html)
        self.assertIn("鍵番号: K-401", html)

    def test_return_get_page(self):
        """鍵返却専用画面の表示テスト"""
        # セキュリティ：該当サークルのメンバーでのログインが必要
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023003'
            sess['user_name'] = '高橋 蓮'

        # コンピュータ研究会 (ID: 2) は初期状態で active (貸出中)
        rv = self.client.get('/club/2/return')
        self.assertEqual(rv.status_code, 200)
        html = rv.data.decode('utf-8')
        self.assertIn("鍵を返す", html)
        self.assertIn("鍵番号: K-402", html)

    def test_settings_page(self):
        """ユーザー設定画面の表示およびお気に入りピン留め表示テスト"""
        # 未ログイン時はログインへリダイレクト
        rv = self.client.get('/settings')
        self.assertEqual(rv.status_code, 302)
        
        # ログインする
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023001'
            sess['user_name'] = '佐藤 太陽'
            
        rv = self.client.get('/settings')
        self.assertEqual(rv.status_code, 200)
        html = rv.data.decode('utf-8')
        self.assertIn("ユーザー設定", html)
        self.assertIn("佐藤 太陽", html)
        self.assertIn("S2023001", html)
        self.assertIn("お気に入りピン留め中", html)
        
        # さらに、従来の /my_clubs が正常に /settings へリダイレクトするか検証
        rv = self.client.get('/my_clubs')
        self.assertEqual(rv.status_code, 302)
        self.assertTrue(rv.location.endswith('/settings'))

    def test_my_clubs_get_page(self):
        """所属サークル設定画面の表示テスト"""
        # 未ログイン時はログインへリダイレクト
        rv = self.client.get('/my_clubs')
        self.assertEqual(rv.status_code, 302)
        
        # ログインする
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023001'
            sess['user_name'] = '佐藤 太陽'
            
        rv = self.client.get('/my_clubs', follow_redirects=True)
        self.assertEqual(rv.status_code, 200)
        html = rv.data.decode('utf-8')
        self.assertIn("ユーザー設定", html)
        self.assertIn("囲碁・将棋・ボードゲーム部", html)

    def test_save_my_clubs_success(self):
        """所属サークルの一括保存（成功系）をテスト"""
        # 佐藤 太陽 (S2023001) は 囲碁・将棋・ボードゲーム部(ID:1, 60日前登録)
        # ログイン
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023001'
            sess['user_name'] = '佐藤 太陽'
            
        # コンピュータ研究会(ID:2)に新規加入し、囲碁・将棋・ボードゲーム部(ID:1)から脱退する（60日前なので許可されるはず）
        rv = self.client.post('/my_clubs/save', data={
            'clubs': ['2'] # 1のチェックを外して2にチェック
        }, follow_redirects=True)
        self.assertEqual(rv.status_code, 200)
        html = rv.data.decode('utf-8')
        self.assertIn("所属サークル設定を更新しました！", html)

    def test_save_my_clubs_locked(self):
        """所属サークルの一括保存（30日退部ロックによるブロック）をテスト"""
        # 鈴木 美咲 (S2023002) は 囲碁・将棋・ボードゲーム部(ID:1, 5日前登録)
        # ログイン
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023002'
            sess['user_name'] = '鈴木 美咲'
            
        # 囲碁・将棋・ボードゲーム部(ID:1)のチェックを外して保存する（5日前登録なのでブロックされるはず）
        rv = self.client.post('/my_clubs/save', data={
            'clubs': []
        }, follow_redirects=True)
        self.assertEqual(rv.status_code, 200) # リダイレクト先で200
        html = rv.data.decode('utf-8')
        self.assertIn("30日間はサークル「囲碁・将棋・ボードゲーム部」の登録解除ができません", html)

    def test_remove_member_locked(self):
        """詳細画面からのメンバー登録解除（30日ロック）をテスト"""
        # ログインする
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023001'
            sess['user_name'] = '佐藤 太陽'

        # 囲碁・将棋・ボードゲーム部(ID:1)に登録されている「鈴木 美咲 (S2023002, 5日前)」を解除しようとすると400エラーになるはず
        rv = self.client.post('/club/1/remove_member', data={
            'student_id': 'S2023002'
        })
        self.assertEqual(rv.status_code, 400)
        json_data = rv.get_json()
        self.assertEqual(json_data['status'], 'error')
        self.assertIn("サークル登録から30日間はメンバー登録の解除ができません", json_data['message'])

        # 囲碁・将棋・ボードゲーム部(ID:1)に登録されている「佐藤 太陽 (S2023001, 60日前)」を解除すると成功するはず
        rv = self.client.post('/club/1/remove_member', data={
            'student_id': 'S2023001'
        })
        self.assertEqual(rv.status_code, 200)
        json_data = rv.get_json()
        self.assertEqual(json_data['status'], 'success')

    def test_quick_status_api(self):
        """クイック状況更新 API (一時施錠・活動再開) のテスト"""
        # 1. 未ログインでのアクセスは401エラーになるはず
        rv = self.client.post('/club/1/quick_status', data={
            'status': 'temp_locked',
            'message': 'ちょっと外出します'
        })
        self.assertEqual(rv.status_code, 401)

        # ログインする (佐藤 太陽: S2023001, 囲碁・将棋・ボードゲーム部 ID:1 のメンバー)
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023001'
            sess['user_name'] = '佐藤 太陽'

        # 2. 鍵が保管中(locked)の状態で状況更新しようとすると400エラーになるはず
        rv = self.client.post('/club/1/quick_status', data={
            'status': 'temp_locked',
            'message': 'ちょっと外出します'
        })
        self.assertEqual(rv.status_code, 400)
        self.assertIn("鍵が保管中のため、状況を変更できません", rv.get_json()['message'])

        # 3. 鍵を借りる (active にする)
        rv = self.client.post('/club/1/borrow', data={
            'student_id': 'S2023001',
            'name': '佐藤 太陽',
            'key_number': 'K-401'
        }, follow_redirects=True)
        self.assertEqual(rv.status_code, 200)

        # 4. 部外者のログインユーザー (田中 葵: S2023004, コンピュータ研究会 ID:2) が
        # 囲碁・将棋・ボードゲーム部 (ID:1) の状況を変更しようとすると403エラーになるはず
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023004'
            sess['user_name'] = '田中 葵'

        rv = self.client.post('/club/1/quick_status', data={
            'status': 'temp_locked',
            'message': 'お昼休み'
        })
        self.assertEqual(rv.status_code, 403)

        # 5. 正しいメンバー (佐藤 太陽) で一時施錠に変更できることを確認 (200 OK)
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023001'
            sess['user_name'] = '佐藤 太陽'

        rv = self.client.post('/club/1/quick_status', data={
            'status': 'temp_locked',
            'message': 'お昼休み'
        })
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.get_json()['status'], 'success')

        # 6. 活動再開に変更できることを確認 (200 OK)
        rv = self.client.post('/club/1/quick_status', data={
            'status': 'active',
            'message': ''
        })
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.get_json()['status'], 'success')

    def test_leader_management_permission(self):
        """部長・副部長以外のメンバーによる管理操作の制限をテスト"""
        # 1. ログインしていない状態での追加・削除・役職変更は401エラーになるはず
        rv = self.client.post('/club/1/add_member', data={
            'student_id': 'S2023999',
            'name': 'テスト ユーザー'
        })
        self.assertEqual(rv.status_code, 401)

        rv = self.client.post('/club/1/remove_member', data={
            'student_id': 'S2023002'
        })
        self.assertEqual(rv.status_code, 401)

        rv = self.client.post('/club/1/change_role', data={
            'student_id': 'S2023002',
            'role': 'president'
        })
        self.assertEqual(rv.status_code, 401)

        # 2. 部長(佐藤 太陽 S2023001)でログインして、テスト一般部員を追加
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023001'
            sess['user_name'] = '佐藤 太陽'

        rv = self.client.post('/club/1/add_member', data={
            'student_id': 'S2023999',
            'name': 'テスト 一般部員'
        })
        self.assertEqual(rv.status_code, 200)

        # 3. 追加した一般部員 (S2023999) でログイン
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023999'
            sess['user_name'] = 'テスト 一般部員'

        # 一般部員がメンバーを追加しようとすると403エラーになるはず
        rv = self.client.post('/club/1/add_member', data={
            'student_id': 'S2023998',
            'name': 'テスト ユーザー'
        })
        self.assertEqual(rv.status_code, 403)
        self.assertIn("メンバー管理権限がありません", rv.get_json()['message'])

        # 一般部員がメンバーを削除しようとすると403エラーになるはず
        rv = self.client.post('/club/1/remove_member', data={
            'student_id': 'S2023002'
        })
        self.assertEqual(rv.status_code, 403)
        self.assertIn("メンバー管理権限がありません", rv.get_json()['message'])

        # 一般部員が役職を変更しようとすると403エラーになるはず
        rv = self.client.post('/club/1/change_role', data={
            'student_id': 'S2023002',
            'role': 'president'
        })
        self.assertEqual(rv.status_code, 403)
        self.assertIn("メンバー管理権限がありません", rv.get_json()['message'])

    def test_change_member_role_success(self):
        """部長による役職変更の成功と引き継ぎ（ハンドオーバー）をテスト"""
        # 囲碁将棋部(ID:1)の部長である佐藤 太陽 (S2023001) でログイン
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023001'
            sess['user_name'] = '佐藤 太陽'

        # 鈴木 美咲 (S2023002) を部長(president)に変更する
        # このとき、元の部長である佐藤 太陽が一般部員に自動降格されることを確認する
        rv = self.client.post('/club/1/change_role', data={
            'student_id': 'S2023002',
            'role': 'president'
        })
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.get_json()['status'], 'success')

        # データベースの状態を確認する
        with self.app.app_context():
            from flaskr.db import get_db
            db_conn = get_db()
            sato = db_conn.execute('SELECT role FROM members WHERE student_id = "S2023001" AND club_id = 1').fetchone()
            suzuki = db_conn.execute('SELECT role FROM members WHERE student_id = "S2023002" AND club_id = 1').fetchone()
            self.assertEqual(sato['role'], 'member')
            self.assertEqual(suzuki['role'], 'president')

    def test_club_messages_permission_and_deletion(self):
        """伝言板メッセージの投稿・削除・権限チェックをテスト"""
        # 1. 未ログインでの投稿はログイン画面へリダイレクト
        rv = self.client.post('/club/1/message', data={'content': 'こんにちは'})
        self.assertEqual(rv.status_code, 302)
        self.assertIn('/login', rv.location)

        # 2. ログインするが、部外者のサークルへの投稿は拒否されることの検証
        # 佐藤太陽 (Club 1) が Club 2 へ投稿
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023001'
            sess['user_name'] = '佐藤 太陽'
        rv = self.client.post('/club/2/message', data={'content': '部外者からのメッセージ'}, follow_redirects=True)
        self.assertEqual(rv.status_code, 200)
        self.assertIn('このサークルのメンバーである必要があります', rv.data.decode('utf-8'))

        # 3. 部員 (鈴木 美咲 Club 1) でログインして、正当なメッセージを投稿
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023002'
            sess['user_name'] = '鈴木 美咲'
        rv = self.client.post('/club/1/message', data={'content': '忘れ物を見つけました！'}, follow_redirects=True)
        self.assertEqual(rv.status_code, 200)
        self.assertIn('忘れ物を見つけました！', rv.data.decode('utf-8'))

        # データベースからメッセージIDを取得
        with self.app.app_context():
            from flaskr.db import get_db
            db_conn = get_db()
            msg = db_conn.execute('SELECT * FROM club_messages WHERE content = "忘れ物を見つけました！"').fetchone()
            self.assertIsNotNone(msg)
            msg_id = msg['id']

        # 4. 別サークルのメンバー (高橋 蓮 Club 2) でログインして、鈴木のメッセージを削除しようとすると拒否されることの検証
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023003'
            sess['user_name'] = '高橋 蓮'
        rv = self.client.post(f'/club/1/delete_message/{msg_id}', follow_redirects=True)
        self.assertEqual(rv.status_code, 200)
        self.assertIn('メッセージを削除する権限がありません', rv.data.decode('utf-8'))

        # 5. 投稿者本人 (鈴木 美咲 S2023002) が削除できることを検証
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023002'
            sess['user_name'] = '鈴木 美咲'
        rv = self.client.post(f'/club/1/delete_message/{msg_id}', follow_redirects=True)
        self.assertEqual(rv.status_code, 200)
        self.assertIn('メッセージを削除しました', rv.data.decode('utf-8'))

        # 6. 部員 (鈴木 美咲) が新たに投稿したメッセージを、部長 (佐藤 太陽) が削除できることを検証
        # 再投稿
        rv = self.client.post('/club/1/message', data={'content': '二回目の投稿'}, follow_redirects=True)
        self.assertEqual(rv.status_code, 200)
        
        with self.app.app_context():
            from flaskr.db import get_db
            db_conn_new = get_db()
            msg2 = db_conn_new.execute('SELECT * FROM club_messages WHERE content = "二回目の投稿"').fetchone()
            msg2_id = msg2['id']

        # 部長 (佐藤 太陽 S2023001) でログインして削除
        with self.client.session_transaction() as sess:
            sess['user_id'] = 'S2023001'
            sess['user_name'] = '佐藤 太陽'
        rv = self.client.post(f'/club/1/delete_message/{msg2_id}', follow_redirects=True)
        self.assertEqual(rv.status_code, 200)
        self.assertIn('メッセージを削除しました', rv.data.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
