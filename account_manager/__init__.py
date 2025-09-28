# account_manager/__init__.py

from db.models import (
    AccountModel, SettingsModel, InfluencerModel,
    TweetModel, ReplyModel, LogModel, AccountInfluencerModel
)

# глобальные объекты моделей (будут инициализироваться init_models)
account_model: AccountModel = None
settings_model: SettingsModel = None
influencer_model: InfluencerModel = None
tweet_model: TweetModel = None
reply_model: ReplyModel = None
log_model: LogModel = None
account_influencer_model: AccountInfluencerModel = None

def init_models(db):
    global account_model, settings_model, influencer_model, tweet_model, reply_model, log_model, account_influencer_model
    account_model = AccountModel(db)
    settings_model = SettingsModel(db)
    influencer_model = InfluencerModel(db)
    tweet_model = TweetModel(db)
    reply_model = ReplyModel(db)
    log_model = LogModel(db)
    account_influencer_model = AccountInfluencerModel(db)

# импорт функций менеджера после инициализации моделей
from .manager import *
