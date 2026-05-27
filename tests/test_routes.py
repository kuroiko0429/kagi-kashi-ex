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
        self.assertIn("ボードゲームサークル", html)

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
        # ボードゲームサークル (ID: 1)
        rv = self.client.get('/club/1')
        self.assertEqual(rv.status_code, 200)
        html = rv.data.decode('utf-8')
        self.assertIn("ボードゲームサークル", html)
        self.assertIn("部屋番号: 401", html)

    def test_borrow_and_return_key(self):
        """鍵の借り出しと返却フローをテスト"""
        # 1. ボードゲームサークル(ID:1)のメンバー「佐藤 太陽 (S2023001)」で借りる
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
        # ボードゲームサークル(ID:1)のメンバー「佐藤 太陽 (S2023001)」で提出
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


if __name__ == '__main__':
    unittest.main()
