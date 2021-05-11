# API REST implementation based on tutorial: https://blog.miguelgrinberg.com/post/designing-a-restful-api-with-python-and-flask

#!flask/bin/python
import os
import random

from flask import Flask, jsonify
from flask import abort
from flask import make_response
from flask import request
from flask import url_for
#from .main.models import db, Hotels, Brief_explanations, Aspects_hotels, Comments, Preferences, Feature_category, Reviews, Actions
from flask import Blueprint

import logging
import pandas as pd
import requests

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, session
from sqlalchemy import func
from sqlalchemy import desc
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
import traceback

db = SQLAlchemy()


logger = logging.getLogger('app')
handler = logging.FileHandler('app.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

app = Flask(__name__)
app.debug = True

bp = Blueprint('main', __name__)
app.register_blueprint(bp)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mydb.sqlite'  # para conectar directamente a sqlite
db.init_app(app)

# configure Session class with desired options
Session = sessionmaker()
engine = create_engine('sqlite:///mydb.sqlite', echo=True, connect_args={"check_same_thread": False})
Session.configure(bind=engine)

# HEROKU os variables ------------------------------------------------------------------------------------
#Endpoints
entities_endpoint = os.environ['ENTITIES_ENDPOINT']
aspect_endpoint = os.environ['ASPECT_ENDPOINT']
subjective_endpoint = os.environ['SUBJECTIVE_ENDPOINT']
comparison_endpoint = os.environ['COMPARISON_ENDPOINT']
detail_endpoint = os.environ['DETAIL_ENDPOINT']
convlog_endpoint = os.environ['CONVLOG_ENDPOINT']
aws_access_key = os.environ['AWS_ACCESS_KEY']
aws_secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY']
aws_region = os.environ['AWS_REGION']
aws_service = os.environ['AWS_SERVICE']

app.config['SECRET_KEY'] = os.environ['SECRET_KEY']

# Heroku API REST authentication
user_gui = os.environ['USER_GUI']
key_gui = os.environ['KEY_GUI']

# HEROKU os variables ------------------------------------------------------------------------------------


# AWS IAM authentication
from aws_requests_auth.aws_auth import AWSRequestsAuth

entities_aws_host = entities_endpoint.split('/')[2]
aspect_aws_host = aspect_endpoint.split('/')[2]
subjective_aws_host = subjective_endpoint.split('/')[2]
comparison_aws_host = comparison_endpoint.split('/')[2]
detail_aws_host = detail_endpoint.split('/')[2]
convlog_aws_host = convlog_endpoint.split('/')[2]
# with app.app_context():
#     db.session.rollback()
#     from .main import routes  # Import routes

determinants = ['this', 'that', 'these', 'those', 'its', 'their', 'any', 'all', 'both', 'either', 'neither', 'each',
                    'every', 'such', 'they', 'it']


# DB Classes ------------------------------------------------------------------------
class Hotels(db.Model):
    hotelID = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    num_reviews = db.Column(db.Integer, default=0)
    price = db.Column(db.Integer, default=0)
    score = db.Column(db.Integer, default=0)
    stars_file = db.Column(db.String(200))
    facilities_summary = db.Column(db.String(100))

    def __repr__(self):
        return '<Hotel %r>' % self.hotelID

class Preferences(db.Model):
    userID = db.Column(db.Integer, primary_key=True)
    pref_0 = db.Column(db.String, primary_key=True)
    pref_1 = db.Column(db.String, primary_key=True)
    pref_2 = db.Column(db.String, primary_key=True)
    pref_3 = db.Column(db.String, primary_key=True)
    pref_4 = db.Column(db.String, primary_key=True)

    def __repr__(self):
        return '<UserID %r>' % self.userID

class Aspects_hotels(db.Model):
    hotelID = db.Column(db.Integer, primary_key=True)
    aspect = db.Column(db.String, primary_key=True)
    comments_positive = db.Column(db.Integer, default=0)
    comments_negative = db.Column(db.Integer, default=0)
    comments_total = db.Column(db.Integer, default=0)
    per_positive = db.Column(db.Integer, default=0)

    def __repr__(self):
        return '<Hotel %r, aspect %r>' % self.hotelID, self.aspect

class Hotel_user_rank(db.Model):
    userID = db.Column(db.Integer, primary_key=True)
    hotelID = db.Column(db.Integer, primary_key=True)
    rank = db.Column(db.Integer, default=0)

    def __repr__(self):
        return '<User %r>' % self.userID

class Brief_explanations(db.Model):
    hotelID = db.Column(db.Integer, primary_key=True)
    userID = db.Column(db.Integer, primary_key=True)
    explanation = db.Column(db.String, default='')

    def __repr__(self):
        return '<Hotel %r, User %r>' % self.hotelID, self.userID

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

class Reviews(db.Model):
    reviewID = db.Column(db.Integer, primary_key=True)
    hotelID = db.Column(db.Integer)
    review_text = db.Column(db.String)
    author = db.Column(db.String)
    score = db.Column(db.Integer)

    def __repr__(self):
        return '<ReviewID %r>' % self.reviewID

class Feature_category(db.Model):
    feature = db.Column(db.String, primary_key=True)
    category = db.Column(db.String, primary_key=True)

    def __repr__(self):
        return '<Feature %r, category %r>' % self.feature, self.category


@app.errorhandler(404)
def not_found(error):
    print(error)
    return make_response(jsonify({'error': 'Not found'}), 404)

# Authentication
from flask_httpauth import HTTPBasicAuth
auth = HTTPBasicAuth()

@auth.get_password
def get_password(username):
    if username == user_gui:
        return key_gui
    return None

@auth.error_handler
def unauthorized():
    return make_response(jsonify({'error': 'Unauthorized access'}), 401)

# Definition of methods
@app.route('/NLU/GetIntention/', methods=['GET'])
@auth.login_required
def get_intention():
    if not request.json or not 'sentence' in request.json:
        abort(400)
    sentence = request.json['sentence']
    sentence_split = sentence.split()
    if 'userID' in request.json:
        userID = request.json['userID']
    else:
        userID = ''
    if 'similar_user' in request.json:
        userID = request.json['similar_user']
    else:
        similar_user = ''
    entities_old = []
    if 'entities_old' in request.json:
        entities_old = request.json['entities_old']
        # TODO: Anaphoras

    if len(sentence.split()) < 3:
        abort(400)
    # wooz_sentences = pd.read_csv('C:\Python\ConversationalRS\data\WoOzSentences.csv', sep='\t')#to check accuracy on WoOz dataset
    # for i, row in wooz_sentences.iterrows(): #to check accuracy on WoOz dataset
    #     sentence = row['Question']
    if True:
        entities_new = []
        error = "" # TODO: Set an appropiate code to respond insufficient number of words to understand question
        scope = assessment = detail = comparison = ""

        try:
            # Pre processing: #TODO: splitting, lower upper case?
            # greetings and thank you

            # Get entities
            auth = AWSRequestsAuth(aws_access_key=aws_access_key, aws_secret_access_key=aws_secret_access_key,
                                   aws_host=entities_aws_host,aws_region=aws_region, aws_service=aws_service)
            response = requests.post(entities_endpoint,json={"sentence": sentence},auth=auth)
            if not response: #or not 'hotels' in request.json:
                abort(400)
            if 'error' in response.json():
                print("Error getting entities:"+response.json().get("error"))
            if 'hotels' in response.json():
                hotels = response.json().get("hotels")
                if len(hotels) > 0:
                    # questions too short: e.g. Hotel Riley. How about hotel Riley.
                    if hotels[0] in ['PERSON', 'GPE']:
                        error = "question_needs_clarification"
                        jsonify({'error': error})
                for i in range(len(hotels)):
                    entities_new.append(hotels[i])
            # Get features
            #TODO

            # Get comparison
            comparison = ""
            sentence = sentence.replace('?',
                                        '')  # workaround, superlative questions are not recognized as superlative when question mark included.
            auth = AWSRequestsAuth(aws_access_key=aws_access_key, aws_secret_access_key=aws_secret_access_key,
                                   aws_host=comparison_aws_host, aws_region=aws_region, aws_service=aws_service)
            response = requests.post(comparison_endpoint, json={"sentence": sentence}, auth=auth)
            if not response:  # or not 'hotels' in request.json:
                abort(400)
            if 'error' in response.json():
                print("Error getting comparison:" + response.json().get("error"))
            if 'type' in response.json():
                comparison = response.json().get("type")
            else:
                comparison = "not_found"
            if comparison == 'non_comparative':
                if ("which" in sentence.lower()) & (("most" in sentence.lower()) | (
                        "nearest" in sentence.lower())):  # Workaround, special cases not recognized as comparative
                    comparison = "comparative"

            # Get scope (possible values: Single, Tuple, Indefinite
            if len(entities_new) == 0:
                if (any([i in sentence for i in determinants])) & (len(entities_old) > 0):
                    entities_new = entities_old
                    if len(entities_old) == 1:
                        scope = 'single'
                    else:
                        scope = 'tuple'
                else:
                    scope = 'indefinite'
            elif len(entities_new) == 1:
                scope = 'single'
                if (comparison == 'comparative') & (any([i in sentence for i in determinants])) & (len(entities_old) > 0):
                    scope = 'tuple'
                    entities_new.extend(entities_old)
            else:
                scope="tuple"

            # Get assessment
            assessment = ""
            sentence_split = sentence.split(" ")
            if ('free' in sentence.lower()) | ('complimentary' in sentence.lower()):
                assessment = "factoid"
            elif ('how are' in sentence.lower()) | ('how is' in sentence.lower()):
                assessment = "subjective"
            else:
                auth = AWSRequestsAuth(aws_access_key=aws_access_key, aws_secret_access_key=aws_secret_access_key,
                                       aws_host=subjective_aws_host,aws_region=aws_region, aws_service=aws_service)
                response = requests.post(subjective_endpoint, json={"sentence": sentence},auth=auth)
                if not response:  # or not 'hotels' in request.json:
                    abort(400)
                if 'error' in response.json():
                    print("Error getting assessment:" + response.json().get("error"))
                if 'type' in response.json():
                    type = response.json().get("type")
                    if type == "non_subjective":
                        assessment = "factoid"
                    else:
                        assessment = "subjective"
                else:
                    assessment = "not_found"
            if "why" in sentence.lower():
                assessment = "why-recommended"

            # if comparative, by default assessment subjective
            if (comparison == 'comparative') & (assessment == 'factoid'):
                assessment = 'subjective'

            # Get Detail
            detail = ""
            auth = AWSRequestsAuth(aws_access_key=aws_access_key, aws_secret_access_key=aws_secret_access_key,
                                   aws_host=detail_aws_host,aws_region=aws_region, aws_service=aws_service)
            response = requests.post(detail_endpoint, json={"sentence": sentence},auth=auth)
            if not response:  # or not 'hotels' in request.json:
                abort(400)
            if 'error' in response.json():
                print("Error getting detail:" + response.json().get("error"))
            if 'detail' in response.json():
                detail = response.json().get("detail")
            else:
                detail = "not_found"
            # Get Aspect
            aspect = ""
            if detail == 'aspect':
                auth = AWSRequestsAuth(aws_access_key=aws_access_key, aws_secret_access_key=aws_secret_access_key,
                                       aws_host=aspect_aws_host, aws_region=aws_region, aws_service=aws_service)
                response = requests.post(aspect_endpoint, json={"sentence": sentence}, auth=auth)
                if not response:  # or not 'hotels' in request.json:
                    abort(400)
                if 'error' in response.json():
                    print("Error getting detail:" + response.json().get("error"))
                if 'aspect' in response.json():
                    aspect = response.json().get("aspect")
                else:
                    aspect = "not_found"

            entity1 = entity2 = aspect1 = aspect2 = "" #TODO: handle entities and aspects
            intention = [{'scope': scope, 'assessment': assessment, 'detail': detail, 'comparison': comparison}]

            # print(sentence + str(entities_new) + str(intention) + " " + str(aspect))
            # Log request
            try:
                auth = AWSRequestsAuth(aws_access_key=aws_access_key, aws_secret_access_key=aws_secret_access_key,
                                       aws_host=convlog_aws_host, aws_region=aws_region, aws_service=aws_service)
                response = requests.post(convlog_endpoint, json={
                        'userID': userID,	'similar_user': similar_user,	'sentence': sentence, 'reply': '',	'action': 'get_intention',	'scope': scope,	'assessment': assessment,	'detail': detail,
                        'comparative': comparison,	'entities': str(entities_new),	'aspect': aspect,	'preferences': '',	'feature': '',	'hotelID': '',	'polarity': ''}, auth=auth)
            except Exception as e:
                print('Error logging: ' + str(e))
                traceback.print_exc()
        except Exception as e:
            print('Error Processing: ' + str(e))
            traceback.print_exc()
            intention=[]

    #TODO: handle not finding an intention
    if len(intention) == 0:
       abort(404)
    return jsonify({'intention': intention[0], 'entities': entities_new, 'aspect': aspect})

@app.route('/ExplainableRS/GetReply/', methods=['GET'])
@auth.login_required
def get_reply():
    if not request.json or not 'sentence' in request.json or not 'intention' in request.json or not 'entities' in request.json or not 'aspect' in request.json or not 'userID' in request.json:
        abort(400)
    sentence = request.json['sentence']
    intention = request.json['intention']
    entities = request.json['entities']
    aspect = request.json['aspect']

    if 'userID' in request.json:
        userID = request.json['userID']
    else:
        userID = ''

    sentence_split = sentence.lower().split()
    scope = intention.get('scope')
    assessment = intention.get('assessment')
    detail = intention.get('detail')
    comparison = intention.get('comparison')

    preferences = []

    reply = ""
    error_code = 0
    feature = "" # only for factoid questions

    # Get most similar user, if not received ---------------------------------------------------------------
    try:
        if 'similar_user' in request.json:
            similar_user = request.json['similar_user']
        elif 'preferences' in request.json:
            preferences = request.json['preferences']
            aspects_all = ['facilities', 'staff', 'room', 'bathroom', 'location', 'price', 'ambience', 'food', 'comfort', 'checking']

            preferences_db = Preferences.query.all()
            common_aspects = pd.DataFrame(columns=['userID', 'common'])
            common_aspects = pd.DataFrame(columns=['userID', 'common'])
            for pref in preferences_db:
                count_occ = 0
                for i in preferences:
                    if i in [pref.pref_0, pref.pref_1, pref.pref_2, pref.pref_3, pref.pref_4]: count_occ += 1
                common_aspects = common_aspects.append(pd.DataFrame({'userID': [pref.userID], 'common': [count_occ]}))

            max_occ = common_aspects['common'].max()
            common_aspects = common_aspects[common_aspects.common == max_occ]
            most_similar = 0
            for idx, row in common_aspects.iterrows():
                preferences_db = Preferences.query.filter(Preferences.userID == row.userID).all()
                if pref.pref_0 == preferences[0]:
                    most_similar = row.userID  # the one with the same first preference

            if most_similar == 0:
                for idx, row in common_aspects.iterrows():
                    if pref.pref_1 == preferences[0]:
                        most_similar = row.userID  # the one with the same second preference
            if most_similar == 0:
                most_similar = common_aspects.iloc[0, :].userID  # first of the most commonalities
            similar_user = most_similar
        else:
            error_code = 103
    except Exception as e:
        error_code = 100
        raise ValueError('Error when getting similar user: ' + str(e))


    # Get first 2 preferences from similar user:------------------------------------------------------------
    try:
        top_prefs = db.session.query(Preferences.pref_0, Preferences.pref_1).filter(Preferences.userID == similar_user).all()
        pref_0 = top_prefs[0][0]
        pref_1 = top_prefs[0][1]
    except Exception as e:
        error_code = 100
        raise ValueError('Error when getting preferences similar user: ' + str(e))

    try:
        # Intentions:
        # single-non_comparative-factoid-aspect -------------------------------------------------------------------
        # tuple - non_comparative - factoid - aspect -------------------------------------------------------------------
        if ((scope == 'single') | (scope == 'tuple')) & (comparison == 'non_comparative') & (assessment == 'factoid') & (detail == 'aspect'):
            try:
                features_aspect = db.session.query(Feature_category.feature). \
                    filter(Feature_category.category == aspect). \
                    all()
                features_aspect_list = []
                for i in features_aspect:
                    features_aspect_list.append(i[0])
                for i in sentence_split:
                    if i in features_aspect_list:
                        feature = i

                # canned statements # TODO: Make more extensive lists
                prices = {'room': '$84', 'food': '$12', 'price': '$40'}
                having = {'facilities': 'Pool, gym, rooms with balcony, restaurant and bar. ',
                          'room': 'Single and double.'}
                old = 'Between 10 and 15 years.'
                ago = '2 years ago.'
                rate = 'It is the 87%. '
                check_time = 'Check-in after 14:00, check-out before 11:00.'
                close = 'About 10 minutes walk.'

                question_w = sentence_split[0]
                if question_w in ['does', 'has', 'is']:
                    reply = 'Yes, it ' + question_w
                    if scope == 'tuple':
                        if len(entities) == 2:
                            reply = 'Yes, both of them'
                        elif len(entities) > 2:
                            reply = 'Yes, all of them'
                elif question_w in ['do', 'have', 'are']:
                    if sentence_split[1] in ['i', 'we']:
                        error_code = 101
                    else:
                        reply = 'Yes, they ' + question_w
                        if scope == 'tuple':
                            if len(entities) == 2:
                                reply = 'Yes, both of them'
                            elif len(entities) > 2:
                                reply = 'Yes, all of them'
                elif question_w == 'how':
                    if (sentence_split[1] == 'much') and (sentence_split[-1] == 'cost'):
                        if prices.get(aspect) is not None:
                            reply = prices.get(aspect) + ' in average'
                    if sentence_split[1] == 'old':
                        reply = old
                    if sentence_split[1] == 'close':
                        reply = close
                elif question_w in ['what', 'whats', 'what\'s']:
                    if sentence_split[-1] in ['has', 'have']:
                        if having.get(aspect) is not None:
                            reply = having.get(aspect)
                    if (sentence_split[1] == 'is') | (question_w in ['whats', 'what\'s']):
                        if prices.get(aspect) is not None:
                            reply = prices.get(aspect)
                        if 'rate' in sentence_split:
                            reply = rate
                    if 'check' in sentence:
                        reply = check_time
                elif question_w == 'when':
                    if sentence_split[1] == 'was':
                        reply = ago
                elif question_w == 'can':
                    reply = 'Yes, you can'

            except Exception as e:
                error_code = 100
                raise ValueError('Error when getting reply intention '+tuple+' - Factoid - Aspect: ' + str(e))

        # Intention single-non_comparative-why-recommended-overall -------------------------------------------------------------------
        # e.g. why is hotel julian my top recommendation
        # Intention single - non_comparative - why-recommended - aspect
        # e.g. why is hotel julian in a good location
        if (scope == 'single') & (comparison == 'non_comparative') & (assessment == 'why-recommended') & ((detail == 'overall') | (detail == 'aspect')):
            # Templates
            template_reply = [
                "Because of the positive comments reported regarding the aspects that matter most to you: _per0_% about _asp0_, and _per1_% about _asp1_. ",
                "Because _per0_% of comments where positive about _asp0_, and _per1_% about _asp1_, both aspects that are relevant to you. ",
                "Because the most important aspects for you were commented positively, _per0_% about _asp0_ and _per1_% about _asp1_. "
            ]
            template_reply_aspect = [
                "_per0_% of comments were positive about _asp0_.",
                "_per0_% of reviews reported positive comments about _asp0_.",
                "About _asp0_, _per0_% of comments were positive.",
            ]
            template_reply_detail_aspect = [
                "Because of the positive comments (_per0_%) reported about _asp0_.",
                "Because _per0_% of comments about _asp0_ were positive.",
            ]
            try:
                # Get hotel id
                hotel_id = ''
                if len(entities) > 0:  # Get hotel id
                    hotel_name = entities[0]
                    if len(entities) == 2:
                        hotel_name = entities[1]
                    hotel_name = hotel_name.split()[-1]
                    hotel_name = hotel_name.title()
                    hotels = db.session.query(Hotels.hotelID, Hotels.name).filter(Hotels.name == hotel_name).all()
                    if len(hotels) > 0:
                        hotel_id = hotels[0][0]

                    if detail == 'overall':
                        # Get quality for aspects and hotel
                        quality = db.session.query(Aspects_hotels.per_positive).filter(Aspects_hotels.hotelID == hotel_id).\
                            filter(Aspects_hotels.aspect == pref_0).all()
                        pref_q0 = str(quality[0][0])
                        quality = db.session.query(Aspects_hotels.per_positive).filter(Aspects_hotels.hotelID == hotel_id). \
                            filter(Aspects_hotels.aspect == pref_1).all()
                        pref_q1 = str(quality[0][0])

                        reply = template_reply[random.randint(0,len(template_reply)-1)]
                        reply = reply.replace('_per0_', pref_q0).replace('_per1_', pref_q1).replace('_asp0_', pref_0).replace('_asp1_', pref_1)
                    else: # intention assessment aspect
                        # TODO: re use this case for Follow up question regarding specific aspect asked by user, but be aware of value received in assessment
                        quality = db.session.query(Aspects_hotels.per_positive).filter(Aspects_hotels.hotelID == hotel_id). \
                            filter(Aspects_hotels.aspect == aspect).all()
                        pref_q0 = str(quality[0][0])
                        reply = template_reply_detail_aspect[random.randint(0, len(template_reply_detail_aspect)-1)]
                        reply = reply.replace('_per0_', pref_q0).replace('_asp0_',aspect)
                else:
                    error_code = 102
            except Exception as e:
                error_code = 100
                raise ValueError('Error when getting reply intention Single - Why - Overall: ' + str(e))

        # Intention indefinite-non_comparative-factoid-aspect
        # e.g. Do any of the hotels offer complimentary breakfast
        if (scope == 'indefinite') & (comparison == 'non_comparative') & (assessment == 'factoid') & (detail == 'aspect'):
            try:
                question_w = sentence_split[0]
                reply = ''

                list_hotels = []
                top_n = 3
                hotels = db.session.query(Hotels.name). \
                    outerjoin(Hotel_user_rank, Hotel_user_rank.hotelID == Hotels.hotelID). \
                    filter(Hotel_user_rank.userID == similar_user). \
                    filter(Hotel_user_rank.rank <= top_n). \
                    all() # TODO: Get list hotels given the feature.

                for i in hotels:
                    list_hotels.append(i[0])

                list_hotels_reply = list_hotels[0:len(list_hotels) if len(list_hotels) < 4 else 3] # reply only list the 3 first hotels with feature.

                if ('do' in sentence_split) | ('any' in sentence_split):
                    if len(list_hotels_reply) > 0:
                        reply = "Yes"
                        if 'is there' in sentence.lower():
                            reply = "Yes, at"
                        for i in list_hotels_reply:
                            reply = reply + ', Hotel ' + i
                        reply = reply.replace('at, Hotel', 'at Hotel')
                    else:
                        reply = "No, according to our information, none."
                elif 'which' in sentence_split:
                    if len(list_hotels_reply) > 0:
                        for i in list_hotels_reply:
                            reply = reply + 'Hotel ' + i + ', '
                    else:
                        reply = "According to our information, none."
            except Exception as e:
                error_code = 100
                raise ValueError('Error when getting reply indefinite-non_comparative-factoid-aspect: ' + str(e))

        # Intention indefinite-comparative-subjective-aspect -----------------------------------------------
        # e.g. which hotel has the best customer service?
        # Intention indefinite - non_comparative - subjective - aspect
        # I just need a good hotel with a gloomy location /  what rooms would be good for parents with children
        if (scope == 'indefinite') & (assessment == 'subjective') & (detail == 'aspect'):
            template_reply = [
                "Hotel _hotel0_, given that  _per0_% of the comments about _asp0_ are positive. _per1_% of the comments of Hotel _hotel1_ are also positive.",
                "Hotel _hotel0_, because  _per0_% of the comments about _asp0_ are positive. Hotel _hotel1_ also has positive comments about it (_per1_%).",
            ]
            top_n = 10 # the best result is limited to top n recommended items
            try:
                #quality = db.session.query(Hotel_user_rank.hotelID ).all()
                quality = db.session.query(Aspects_hotels.per_positive, Hotel_user_rank.hotelID, Hotels.name). \
                    outerjoin(Hotel_user_rank, Hotel_user_rank.hotelID == Aspects_hotels.hotelID). \
                    outerjoin(Hotels, Hotel_user_rank.hotelID == Hotels.hotelID). \
                    filter(Aspects_hotels.aspect == aspect). \
                    filter(Hotel_user_rank.userID == similar_user). \
                    filter(Hotel_user_rank.rank <= top_n). \
                    order_by(desc(Aspects_hotels.per_positive)). \
                    all()
                hotel_0 = quality[0][2]
                percentage_0 = str(quality[0][0])
                hotel_1 = quality[1][2]
                percentage_1 = str(quality[1][0])
                reply = template_reply[random.randint(0, len(template_reply) - 1)]
                reply = reply.replace('_hotel0_', hotel_0).replace('_per0_', percentage_0).replace('_asp0_', aspect).replace('_hotel1_',hotel_1).replace('_per1_',percentage_1)
            except Exception as e:
                error_code = 100
                raise ValueError('Error when getting reply intention Comparison Indefinite - Evaluation - Aspect: ' + str(e))

            # Intention Single - Subjective - Aspect ----------------------------------------------------------
            # e.g. How is the food at Hotel Evelyn?

        # Intention single-non_comparative-subjective-aspect ----------------------------------------------------------------
        # e.g. How is the food at Hotel Evelyn
        if (scope == 'single') & (comparison == 'non_comparative') & (assessment == 'subjective') & (detail == 'aspect'):
            template_reply = [
                "_per0_% of the comments about _asp0_ are positive.",
                "Comments about _asp0_ are mostly positive (_per0_%).",
            ]
            try:
                hotel_id = ''
                if len(entities) > 0:  # Get hotel id
                    hotel_name = entities[0]
                    if len(entities) == 2:
                        hotel_name = entities[1]
                    hotel_name = hotel_name.split()[-1]
                    hotel_name = hotel_name.title()
                    hotels = db.session.query(Hotels.hotelID, Hotels.name).filter(Hotels.name == hotel_name).all()
                    if len(hotels) > 0:
                        hotel_id = hotels[0][0]
                    quality = db.session.query(Aspects_hotels.per_positive). \
                        filter(Aspects_hotels.hotelID == hotel_id). \
                        filter(Aspects_hotels.aspect == (aspect if not aspect == 'none' else 'room')).all()
                    percentage = str(quality[0][0])
                    reply = template_reply[random.randint(0, len(template_reply) - 1)]
                    reply = reply.replace('_per0_', percentage).replace('_asp0_', (aspect if not aspect == 'none' else 'it'))

                else:
                    error_code = 100
            except Exception as e:
                error_code = 100
                raise ValueError('Error when getting reply intention Single - Subjective - Aspect: ' + str(e))

        # Intention indefinite-comparative-subjective-overall ----------------------------------------------------------------
        # e.g. which hotels have the best reviews / Which hotel is the best of these 5
        # Intention indefinite - non_comparative - subjective - overall ( could be treated exactly as Intention indefinite-comparative-subjective-overall, very low frequency)
        # what would be a good recomendation
        if (scope == 'indefinite') & ((comparison == 'comparative') | (comparison == 'non_comparative')) & (assessment == 'subjective') & (detail == 'overall'):
            # Templates
            template_reply = [
                "Hotel _hotel1_ has the best reviews and ratings. _per1_% of the comments are positive. ",
                "The best reviews and ratings were reported for Hotel _hotel1_ (_per1_% of positive comments). ",
                "Hotel _hotel1_, based on the ratings and mostly positive comments reported (about _per1_% of positive comments). ",
            ]
            try:
                top_n = 5
                reply = ''
                quality = db.session.query(Hotels.name, func.avg(Aspects_hotels.per_positive).label('average_pos')). \
                    outerjoin(Hotel_user_rank, Hotel_user_rank.hotelID == Aspects_hotels.hotelID). \
                    outerjoin(Hotels, Hotel_user_rank.hotelID == Hotels.hotelID). \
                    filter(Hotel_user_rank.userID == similar_user). \
                    filter(Hotel_user_rank.rank < top_n). \
                    all()
                hotel_1 = quality[0][0]
                percentage_1 = str(round(quality[0][1]))

                reply = template_reply[random.randint(0, len(template_reply) - 1)]
                reply = reply.replace('_hotel1_', hotel_1).replace('_per1_', percentage_1)
            except Exception as e:
                error_code = 100
                raise ValueError('Error when getting reply intention indefinite-comparative-subjective-overall: ' + str(e))

        # Intention tuple - comparative - subjective - overall
        # what is difference between hotel evelyn and hotel james
        # Intention 'tuple - comparative - why-recommended - overall' will be handled equal to 'tuple - comparative - subjective - overall'
        # e.g. Why is it better than Hotel Riley
        # Intention tuple - comparative - why-recommended - aspect
        # e.g. Why is Julian location better than Hotel Riley
        if (scope == 'tuple') & (comparison == 'comparative') & ((assessment == 'subjective') | (assessment == 'why-recommended')):
            #& (detail == 'overall')
            #& (detail == 'aspect')
            try:
                reply = ""
                if len(entities) > 1:
                    hotel_1 = entities[0].split()[-1].title()
                    hotel_2 = entities[1].split()[-1].title()

                    # rank = db.session.query(Hotels.name, Hotels.score, Hotel_user_rank.rank). \
                    #     outerjoin(Hotel_user_rank, Hotel_user_rank.hotelID == Hotels.hotelID). \
                    #     filter(or_(Hotels.name == hotel_1, Hotels.name == hotel_2)). \
                    #     filter(Hotel_user_rank.userID == similar_user). \
                    #     all()
                    if detail == 'overall':
                        pref = db.session.query(Preferences.pref_0, Preferences.pref_1, Preferences.pref_2, Preferences.pref_3, Preferences.pref_4).\
                            filter(Preferences.userID == similar_user).all()
                        preferences = []
                        for i in pref[0]:
                            preferences.append(i)
                    else:
                        preferences = [aspect]
                    quality_pref = db.session.query(Hotels.name, Aspects_hotels.aspect, Aspects_hotels.per_positive). \
                        outerjoin(Aspects_hotels, Hotels.hotelID == Aspects_hotels.hotelID). \
                        filter(or_(Hotels.name == hotel_1, Hotels.name == hotel_2)). \
                        filter(Aspects_hotels.aspect.in_(preferences)).all()
                    quality_pref_df = pd.DataFrame(columns={'hotel', 'aspect', 'per_positive'})
                    for i in quality_pref:
                        quality_pref_df = quality_pref_df.append(pd.DataFrame({'hotel': [i[0]], 'aspect': [i[1]], 'per_positive': [i[2]]}))
                    #print(quality_pref_df)

                    better_h1 = []
                    better_h2 = []
                    for i in preferences:
                        if quality_pref_df[(quality_pref_df.aspect == i) & (quality_pref_df.hotel == hotel_1)][
                            'per_positive'].values[0] > \
                                quality_pref_df[(quality_pref_df.aspect == i) & (quality_pref_df.hotel == hotel_2)][
                                    'per_positive'].values[0]:
                            better_h1.append(i)
                        else:
                            better_h2.append(i)
                    best_hotel = hotel_1 if len(better_h1) > len(better_h2) else hotel_2
                    if detail == 'overall':
                        if (len(better_h1) == 0) | (len(better_h2) == 0):
                            reply = 'Hotel ' + best_hotel + ' has better comments about the most important aspects to you (' + str(preferences) + ')'
                            reply = reply.replace('[', '').replace(']', '').replace('\'', '')
                        else:
                            if len(better_h1) > len(better_h2):
                                reply = 'Hotel _hotel1_ has better comments on the aspects that are most important to you (' + str(better_h1) + '). However, Hotel _hotel2_ has better comments about ' + str(better_h2) + '.'
                            elif len(better_h1) < len(better_h2):
                                reply = '_hotel2_ has better comments on the aspects that are most important to you (' + str(better_h2) + '). However _hotel1_ has better comments about ' + str(better_h1) + '.'
                            reply = reply.replace('_hotel1_', hotel_1).replace('_hotel2_',hotel_2).replace('[','').replace(']','').replace('\'','')
                    else:
                        reply = 'Hotel ' + best_hotel + ' has better comments about '+ aspect + ' ('+str(quality_pref_df[quality_pref_df.hotel==best_hotel]['per_positive'].values[0]) + '% of positive comments)'
                        # TODO: e.g. why is hotel evelyn a 4 star hotel priced higher than hotel owen a 5star hotel
                else:
                    error_code = 102
            except Exception as e:
                error_code = 100
                raise ValueError('Error when getting reply intention tuple - comparative - subjective - overall: ' + str(e))

        # From here, only intentions with very low frequency ------------------

        # Intention indefinite - comparative - factoid - aspect
        # which the nearest hotel to a station
        if (scope == 'indefinite') & (comparison == 'comparative') & (assessment == 'factoid') & (detail == 'aspect'):
            top_n = 5 # the best result is limited to top n recommended items
            try:
                #quality = db.session.query(Hotel_user_rank.hotelID ).all()
                quality = db.session.query(Aspects_hotels.per_positive, Hotel_user_rank.hotelID, Hotels.name). \
                    outerjoin(Hotel_user_rank, Hotel_user_rank.hotelID == Aspects_hotels.hotelID). \
                    outerjoin(Hotels, Hotel_user_rank.hotelID == Hotels.hotelID). \
                    filter(Aspects_hotels.aspect == aspect). \
                    filter(Hotel_user_rank.userID == similar_user). \
                    filter(Hotel_user_rank.rank <= top_n). \
                    order_by(desc(Aspects_hotels.per_positive)). \
                    all()
                print(quality[0][2])
                hotel_0 = quality[0][2]
                reply = 'Hotel '+ hotel_0
            except Exception as e:
                error_code = 100
                raise ValueError('Error when getting reply intention Comparison Indefinite - Evaluation - Aspect: ' + str(e))

        # Intention indefinite - non_comparative - NA - indefinite
        # why are there so few reviews
        # TODO: For now, it will reply no sufficient info

    except ValueError as err:
        error_description = err.message
    except Exception as e:
        error_code = 100
        error_description = 'Error when getting preferences similar user: ' + str(e)
    finally:
        db.session.close()

    error = {}
    if error_code == 100:
        error = {'error_code': 100,'error_description': error_description}
    if (error_code == 101) | (reply == ''):
        error = {'error_code': 101, 'error_description':'I am sorry, I do not have enough information to reply to this question.'}
    if (error_code == 102) :
        error = {'error_code': 102, 'error_description':'Could you please indicate the name of the hotel for which you would like information?'}
    if (error_code == 103) :
        error = {'error_code': 103, 'error_description':'Please indicate the aspects of most importance to you.'}
    if (len(error) > 0) & (not aspect == 'reply_assessment') :
        return jsonify(error)

    # Log request
    try:
        auth = AWSRequestsAuth(aws_access_key=aws_access_key, aws_secret_access_key=aws_secret_access_key,
                               aws_host=convlog_aws_host, aws_region=aws_region, aws_service=aws_service)
        response = requests.post(convlog_endpoint, json={
            'userID': userID, 'similar_user': similar_user, 'sentence': sentence, 'reply': reply, 'action': 'get_reply',
            'scope': scope, 'assessment': assessment, 'detail': detail,
            'comparative': comparison, 'entities': str(entities), 'aspect': aspect, 'preferences': str(preferences),
            'feature': '', 'hotelID': '', 'polarity': ''}, auth=auth)
    except Exception as e:
        print('Error logging: ' + str(e))
        traceback.print_exc()

    except Exception as e:
        print('Error logging: ' + str(e))
        traceback.print_exc()
    if not sentence is None:
        return jsonify({'reply': reply, 'similar_user': similar_user, 'feature': feature})
    else:
        return jsonify({'error_code': 104, 'error_description': 'A question is required.'})

@app.route('/ExplainableRS/GetRecommendations/', methods=['GET'])
@auth.login_required
def get_recommendations():
    if ((not request.json) | (not('preferences' in request.json) | ('similar_user' in request.json))):
        abort(400)

    # If not received Get most similar user using preferences
    if 'similar_user' in request.json:
        if not (request.json['similar_user'] == ''):
            similar_user = request.json['similar_user']
    else:
        preferences = request.json['preferences']
        similar_user = get_similar_user(preferences)
    top_n = 10  # the best result is limited to top n recommended items
    try:
        hotels = db.session.query(Hotels.hotelID, Hotels.name, Hotels.score, Hotels.num_reviews, Hotels.price, Hotels.stars_file, Hotels.facilities_summary,
                                  Brief_explanations.explanation). \
            outerjoin(Hotel_user_rank, Hotels.hotelID == Hotel_user_rank.hotelID). \
            outerjoin(Brief_explanations, Hotels.hotelID == Brief_explanations.hotelID). \
            filter(Hotel_user_rank.userID == similar_user). \
            filter(Brief_explanations.userID == similar_user). \
            filter(Hotel_user_rank.rank <= top_n). \
            order_by(Hotel_user_rank.rank). \
            all()
        recommendations = []
        for i in hotels:
            hotel = {'hotelID': i[0], 'name': 'Hotel ' + i[1], 'score': i[2], 'n_reviews': i[3], 'price': '$' + str(i[4]), 'stars_file': i[5],
                      'room_file': 'room'+str(i[0]%10)+'.png', 'location_file': 'location'+str(i[0]%10)+'.png', 'facilities_summary': i[6], 'brief_explanation': i[7]}
            recommendations.append(hotel)
    except Exception as e:
        print(e)
        error_code = 100
        error_description = 'Error when getting recommendations: ' + str(e)
    finally:
        db.session.close()

    #TODO: handle not finding recommendations
    #if len(intention) == 0:
    #    abort(404)
    return jsonify({'recommendations': recommendations}) #returns list of comments

def get_similar_user(preferences):
# Get most similar user, if not received ---------------------------------------------------------------
    try:
        aspects_all = ['facilities', 'staff', 'room', 'bathroom', 'location', 'price', 'ambience', 'food', 'comfort', 'checking']

        preferences_db = Preferences.query.all()
        common_aspects = pd.DataFrame(columns=['userID', 'common'])
        common_aspects = pd.DataFrame(columns=['userID', 'common'])
        for pref in preferences_db:
            count_occ = 0
            for i in preferences:
                if i in [pref.pref_0, pref.pref_1, pref.pref_2, pref.pref_3, pref.pref_4]: count_occ += 1
            common_aspects = common_aspects.append(pd.DataFrame({'userID': [pref.userID], 'common': [count_occ]}))

        max_occ = common_aspects['common'].max()
        common_aspects = common_aspects[common_aspects.common == max_occ]
        most_similar = 0
        for idx, row in common_aspects.iterrows():
            preferences_db = Preferences.query.filter(Preferences.userID == row.userID).all()
            if pref.pref_0 == preferences[0]:
                most_similar = row.userID  # the one with the same first preference

        if most_similar == 0:
            for idx, row in common_aspects.iterrows():
                if pref.pref_1 == preferences[0]:
                    most_similar = row.userID  # the one with the same second preference
        if most_similar == 0:
            most_similar = common_aspects.iloc[0, :].userID  # first of the most commonalities
        return  most_similar

    except Exception as e:
        error_code = 100
        error_description = 'Error when getting similar user: ' + str(e)
    finally:
        print("I will close the session")
        db.session.close()


@app.route('/ExplainableRS/GetReviews/', methods=['GET'])
@auth.login_required
def get_reviews():
    if (not request.json) | (not 'hotelID' in request.json):
        abort(400)
    hotelID = request.json['hotelID']
    try:
        reviews = db.session.query(Reviews.hotelID, Reviews.score, Reviews.review_text, Reviews.author). \
            filter(Reviews.hotelID == hotelID). \
            all()
        reviews_list = []
        for i in reviews:
            review = {'hotelID': i[0], 'review_score': i[1], 'review_text': i[2], 'review_author': i[3]}
            reviews_list.append(review)
    except Exception as e:
        print(e)
        error_code = 100
        error_description = 'Error when getting reviews: ' + str(e)
    finally:
        db.session.close()

    #TODO: handle not finding recommendations
    #if len(intention) == 0:
    #    abort(404)
    return jsonify({'reviews': reviews_list}) #returns list of reviews

@app.route('/ExplainableRS/GetComments/', methods=['GET'])
@auth.login_required
def get_comments():
    if (not request.json) | (not 'hotelID' in request.json) | (not 'aspect' in request.json):
        abort(400)
    hotelID = request.json['hotelID']
    aspect = request.json['aspect']
    if 'polarity' in request.json:
        polarity = request.json['polarity']
    else:
        polarity = 'all'
    if 'specific_feature' in request.json:
        aspect_ = request.json['specific_feature']
    else:
        aspect_ = aspect

    try:
        if not polarity == 'all':
            comments = db.session.query(Comments.hotelID, Comments.author, Comments.score, Comments.sentence, Comments.polarity, Comments.feature). \
                filter(Comments.hotelID == hotelID). \
                filter(Comments.feature == aspect_). \
                filter(Comments.polarity == polarity). \
                order_by(desc(Comments.score)). \
                all()
        else:
            comments = db.session.query(Comments.hotelID, Comments.author, Comments.score, Comments.sentence,
                                        Comments.polarity, Comments.feature). \
                filter(Comments.hotelID == hotelID). \
                filter(Comments.feature == aspect). \
                order_by(desc(Comments.score)). \
                all()
        print(comments)
        comments_list = []
        for i in comments:
            comment = {'hotelID': i[0], 'comment_author': i[1], 'comment': i[3], 'polarity': i[4]}
            comments_list.append(comment)

        comments_features = db.session.query(func.count(Comments.sentence).label("num_comments"), Comments.feature). \
            outerjoin(Feature_category, Comments.feature == Feature_category.feature). \
            filter(Comments.hotelID == hotelID). \
            filter(Feature_category.category == aspect). \
            filter(Comments.category_f == 0). \
            filter(Comments.polarity == polarity). \
            group_by(Comments.feature). \
            order_by(desc(func.count(Comments.sentence))). \
            all()
        # print("most commented feat:" + comments_features[0].feature + ": " + str(comments_features[0].num_comments))
        # print("least commented feat:" + comments_features[-1].feature + ": " + str(comments_features[-1].num_comments))
        most_comm_features = []
        if len(comments_features) > 3:
            num_buttons = 4
        else:
            num_buttons = len(comments_features)

        for i in range(0, num_buttons):
            most_comm_features.append(comments_features[i].feature)
        print(most_comm_features)
    except Exception as e:
        error_code = 100
        error_description = 'Error when getting comments: ' + str(e)
    finally:
        db.session.close()

    #TODO: handle not finding recommendations
    #if len(intention) == 0:
    #    abort(404)
    return jsonify({'comments': comments_list, 'most_comm_features':most_comm_features}) #returns list of reviews

@app.route('/ExplainableRS/GetHotelsFeature/', methods=['GET'])
@auth.login_required
def get_hotels_feature():
    if ((not request.json) | (not 'feature' in request.json) | (not ('preferences' in request.json) | ('similar_user' in request.json))):
        abort(400)

    # If not received Get most similar user using preferences
    if 'similar_user' in request.json:
        if not (request.json['similar_user'] == ''):
            similar_user = request.json['similar_user']
    else:
        preferences = request.json['preferences']
        similar_user = get_similar_user(preferences)
    top_n = 10  # the best result is limited to top n recommended items
    num_items_return = 7
    try:
        hotels = db.session.query(Hotels.hotelID). \
            outerjoin(Hotel_user_rank, Hotels.hotelID == Hotel_user_rank.hotelID). \
            filter(Hotel_user_rank.userID == similar_user). \
            filter(Hotel_user_rank.rank <= top_n). \
            order_by(Hotel_user_rank.rank). \
            all()
        hotels_list = []
        for i in hotels:
            hotels_list.append(i[0])
        hotels_list = random.sample(hotels_list, num_items_return)
    except Exception as e:
        print(e)
        error_code = 100
        error_description = 'Error when getting recommendations: ' + str(e)
    finally:
        db.session.close()

    # TODO: handle not finding recommendations
    # if len(intention) == 0:
    #    abort(404)
    return jsonify({'hotels': hotels_list})  # returns list of hotels

@app.route('/ExplainableRS/Log/', methods=['POST'])
@auth.login_required
def log_message():
    if (not request.json) | (not 'message' in request.json):
        abort(400)
    else:
        message = request.json['message']
        # Log request
        try:
            auth = AWSRequestsAuth(aws_access_key=aws_access_key, aws_secret_access_key=aws_secret_access_key,
                                   aws_host=convlog_aws_host, aws_region=aws_region, aws_service=aws_service)
            response = requests.post(convlog_endpoint, json={'message': message}, auth=auth)
        except Exception as e:
            print('Error logging: ' + str(e))
            traceback.print_exc()
            return jsonify({'error': str(e)})  # returns list of hotels
    return jsonify({'log': 'registered'})  # returns list of hotels


if __name__ == '__main__':
    app.run(debug=True)


