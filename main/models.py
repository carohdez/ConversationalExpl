# Database model

from app import db
from datetime import datetime

class Hotels(db.Model):
    hotelID = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    num_reviews = db.Column(db.Integer, default=0)
    price = db.Column(db.Integer, default=0)
    score = db.Column(db.Integer, default=0)
    stars_file = db.Column(db.String(200))

    def __repr__(self):
        return '<Hotel %r>' % self.hotelID


class Brief_explanations(db.Model):
    hotelID = db.Column(db.Integer, primary_key=True)
    userID = db.Column(db.Integer, primary_key=True)
    explanation = db.Column(db.String, default='')

    def __repr__(self):
        return '<Hotel %r, User %r>' % self.hotelID, self.userID


class Aspects_hotels(db.Model):
    hotelID = db.Column(db.Integer, primary_key=True)
    aspect = db.Column(db.String, primary_key=True)
    comments_positive = db.Column(db.Integer, default=0)
    comments_negative = db.Column(db.Integer, default=0)
    comments_total = db.Column(db.Integer, default=0)
    per_positive = db.Column(db.Integer, default=0)

    def __repr__(self):
        return '<Hotel %r, aspect %r>' % self.hotelID, self.aspect


class Comments(db.Model):
    hotelID = db.Column(db.Integer, primary_key=True)
    reviewID = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.Integer)
    score = db.Column(db.Integer)
    sentence = db.Column(db.Integer)
    feature = db.Column(db.Integer, primary_key=True)
    polarity = db.Column(db.Integer)
    category_f = db.Column(db.Integer)

    def __repr__(self):
        return '<Hotel %r, review %r, feature %r>' % self.hotelID, self.reviewID, self.feature


class Preferences(db.Model):
    userID = db.Column(db.Integer, primary_key=True)
    pref_0 = db.Column(db.String, primary_key=True)
    pref_1 = db.Column(db.String, primary_key=True)
    pref_2 = db.Column(db.String, primary_key=True)
    pref_3 = db.Column(db.String, primary_key=True)
    pref_4 = db.Column(db.String, primary_key=True)

    def __repr__(self):
        return '<UserID %r>' % self.userID


class Feature_category(db.Model):
    feature = db.Column(db.String, primary_key=True)
    category = db.Column(db.String, primary_key=True)

    def __repr__(self):
        return '<Feature %r, category %r>' % self.feature, self.category


class Reviews(db.Model):
    reviewID = db.Column(db.Integer, primary_key=True)
    hotelID = db.Column(db.Integer)
    review_text = db.Column(db.String)
    author = db.Column(db.String)
    score = db.Column(db.Integer)

    def __repr__(self):
        return '<ReviewID %r>' % self.reviewID


class Actions(db.Model):
    actionID = db.Column(db.Integer, primary_key=True)
    action_type = db.Column(db.String)
    page = db.Column(db.String)
    feature = db.Column(db.String)
    description = db.Column(db.String)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    workerID = db.Column(db.String)
    userID = db.Column(db.Integer)
    condition = db.Column(db.Integer)
    hotelID = db.Column(db.Integer)
    reviewID = db.Column(db.Integer)
    back = db.Column(db.Integer, default=0)

    def __repr__(self):
        return '<Back %r>' % self.back