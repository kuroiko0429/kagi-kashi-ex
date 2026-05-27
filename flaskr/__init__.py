import os

from flask import Flask, render_template


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

    # ページの表示
    @app.route('/')
    def hello():
        keys = [
            {'id':24, 'name':"ボードゲーム", 'state':0, 'comment':""},
            {'id':24, 'name':"ボードゲーム", 'state':1, 'comment':""},
            {'id':24, 'name':"ボードゲーム", 'state':0, 'comment':""},
            {'id':24, 'name':"ボードゲーム", 'state':1, 'comment':""},
            {'id':24, 'name':"ボードゲーム", 'state':1, 'comment':""},
            {'id':24, 'name':"ボードゲーム", 'state':0, 'comment':""},
            {'id':24, 'name':"ボードゲーム", 'state':1, 'comment':""},
            {'id':24, 'name':"ボードゲーム", 'state':0, 'comment':""},
            {'id':24, 'name':"ボードゲーム", 'state':1, 'comment':""},
            {'id':24, 'name':"ボードゲーム", 'state':1, 'comment':""},
            {'id':24, 'name':"ボードゲーム", 'state':0, 'comment':""},
            {'id':24, 'name':"ボードゲーム", 'state':0, 'comment':""},
            {'id':24, 'name':"ボードゲーム", 'state':1, 'comment':""}
        ]
        return render_template('index.html', keys=keys)

    return app