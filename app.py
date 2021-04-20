# API REST implementation based on tutorial: https://blog.miguelgrinberg.com/post/designing-a-restful-api-with-python-and-flask

#!flask/bin/python
import os

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
import traceback

db = SQLAlchemy()

logger = logging.getLogger('app')
handler = logging.FileHandler('app.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

app = Flask(__name__)


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
# with app.app_context():
#     db.session.rollback()
#     from .main import routes  # Import routes

wooz_sentences = pd.read_csv('C:\Python\ConversationalRS\data\WoOzSentences.csv', sep='\t')#to check accuracy on WoOz dataset
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
    if len(sentence.split()) < 3:
        abort(400)
    for i, row in wooz_sentences.iterrows(): #to check accuracy on WoOz dataset
        sentence = row['Question']
        entities_new = []
        error = "" # TODO: Set an appropiate code to respond insufficient number of words to understand question
        scope = assessment = detail = comparison = ""

        # entity1 = request.json['entity1']
        # entity2 = request.json['entity2']
        # feature1 = request.json['feature1']
        # feature2 = request.json['feature2']

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
            # Get scope (possible values: Single, Tuple, Indefinite
            if len(entities_new) == 1:
                scope="single"
            elif len(entities_new) == 0:
                scope="indefinite"
            else:
                scope="tuple"

            # Get comparison
            comparison = ""
            sentence = sentence.replace('?','') # workaround, superlative questions are not recognized as superlative when question mark included.
            auth = AWSRequestsAuth(aws_access_key=aws_access_key, aws_secret_access_key=aws_secret_access_key,
                                   aws_host=comparison_aws_host,aws_region=aws_region, aws_service=aws_service)
            response = requests.post(comparison_endpoint, json={"sentence": sentence},auth=auth)
            if not response:  # or not 'hotels' in request.json:
                abort(400)
            if 'error' in response.json():
                print("Error getting comparison:" + response.json().get("error"))
            if 'type' in response.json():
                comparison = response.json().get("type")
            else:
                comparison = "not_found"
            if comparison == 'non_comparative':
                if ("which" in sentence.lower()) & (("most" in sentence.lower()) | ("nearest" in sentence.lower())): # Workaround, special cases not recognized as comparative
                    comparison = "comparative"



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

            # TODO: Handle time out of aws services
            entity1 = entity2 = aspect1 = aspect2 = "" #TODO: handle entities and aspects
            #intention = [{'scope':scope, 'assessment':assessment, 'detail':detail, 'entity1':"", 'entity2':"", 'feature1':"", 'feature2':"" }]
            intention = [{'scope': scope, 'assessment': assessment, 'detail': detail, 'comparison': comparison}]

            print(sentence + str(entities_new) + str(intention) + " " + str(aspect))
        except Exception as e:
            print('Error Processing: ' + str(e))
            traceback.print_exc()
            intention=[]

    #TODO: handle not finding an intention
    if len(intention) == 0:
       abort(404)
    return jsonify({'intention': intention[0], 'entities_new': entities_new, 'aspect': aspect})

@app.route('/ExplainableRS/GetReply/', methods=['GET'])
def get_reply():
    if not request.json or not 'sentence' in request.json:
        abort(400)
    sentence = request.json['sentence']
    scope = assessment = detail = ""
    reply = ""
    if sentence == 'Does Hotel Julian have a pool?':
        scope = "single"
        assessment = "factoid"
        detail = "aspect"
    else:
        scope = "other_s"
        assessment = "other_a"
        detail = "other_d"
    if (scope == "single") & (scope == "factoid") & (scope == "aspect"):
        #type = "YN" #get_type(sentence) # TODO: get type of factoid
        reply = "Yes"
    else:
        reply= "No"
    reply = [{'reply':reply}]
    #TODO: handle not finding a reply
    #if len(intention) == 0:
    #    abort(404)
    return jsonify({'reply': reply[0]})

@app.route('/ExplainableRS/GetHotelsFeature/', methods=['GET'])
def get_hotels_feature():
    if not request.json or not 'feature' in request.json:
        abort(400)
    feature = request.json['feature']
    hotels = [{'hotelID':123}, {'hotelID':456}, {'hotelID':678}]
    #TODO: handle not finding an hotels with such feature
    #if len(intention) == 0:
    #    abort(404)
    return jsonify({'hotels': hotels})

@app.route('/ExplainableRS/GetComments/', methods=['GET'])
def get_comments():
    if not request.json or not 'hotelID' in request.json or not 'feature' in request.json:
        abort(400)
    hotelID = request.json['hotelID']
    feature = request.json['feature']
    polarity = request.json['polarity']

    # comments = get_comments(hotelID, feature, polarity)
    comment = 'i think th pool was fantastic!'
    comments = [{'comment':comment, 'polarity': polarity}]
    #TODO: handle not finding comments
    #if len(intention) == 0:
    #    abort(404)
    return jsonify({'comments': comments}) #returns list of comments

@app.route('/ExplainableRS/GetRecommendations/', methods=['GET'])
def get_recommendations():
    # if not request.json or not 'hotelID' in request.json or not 'feature' in request.json:
    #     abort(400)

    hotelID = 123
    hotel_name = 'Hotel Hilton'
    rating = 4.5
    n_reviews = 25
    brief_explanation = 'Good food, nice view.'
    metadata = 'Beatiful hotel, with AC, spa and bar'
    hotel1 = {'hotelID': hotelID, 'rating': rating, 'n_reviews': n_reviews, 'brief_explanation': brief_explanation, 'metadata': metadata}

    hotelID = 123
    hotel_name = 'Hotel Intercontinental'
    rating = 4.5
    n_reviews = 25
    brief_explanation = 'Good rooms, nice restaurant.'
    metadata = 'Big rooms with AC, balcon and minibar'
    hotel2 = {'hotelID': hotelID, 'rating': rating, 'n_reviews': n_reviews, 'brief_explanation': brief_explanation,'metadata': metadata}

    recommendations = [hotel1, hotel2]

    #TODO: handle not finding recommendations
    #if len(intention) == 0:
    #    abort(404)
    return jsonify({'recommendations': recommendations}) #returns list of comments

#--------------------

# Method to obtain recommendations based on user preferences
# @app.route('/recommendations/', methods=['GET'])
# def get_recommendations_():
#     if not request.json or not 'pref_1' in request.json:
#         abort(400)
#
#         preferences_in = [request.json['pref_1'], request.json['pref_2'], request.json['pref_2'],
#                           request.json['pref_3'],
#                           request.json['pref_4'], request.json['pref_5']]
#
#     # Infer user with similar preferences to our participant
#     try:
#         preferences = Preferences.query.all()  # get list of users in users pref matrix, if userID and their preferences (0 to 4)
#
#         common_aspects = pd.DataFrame(columns=['userID', 'common'])
#         for pref in preferences:
#             count_occ = 0
#             for i in preferences_in:
#                 if i in [pref.pref_0, pref.pref_1, pref.pref_2, pref.pref_3, pref.pref_4]: count_occ += 1
#             common_aspects = common_aspects.append(pd.DataFrame({'userID': [pref.userID], 'common': [count_occ]}))
#
#         max_occ = common_aspects['common'].max()
#         common_aspects = common_aspects[common_aspects.common == max_occ]
#         most_similar = 0
#         for idx, row in common_aspects.iterrows():
#             preferences = Preferences.query.filter(Preferences.userID == row.userID).all()
#             if pref.pref_0 == preferences_in[0]:
#                 most_similar = row.userID  # the one with the same first preference
#
#         if most_similar == 0:
#             for idx, row in common_aspects.iterrows():
#                 if pref.pref_1 == preferences_in[0]:
#                     most_similar = row.userID  # the one with the same second preference
#         if most_similar == 0:
#             most_similar = common_aspects.iloc[0, :].userID  # first of the most commonalities
#
#     except Exception as e:
#         print('Error Processing user preferences: ' + str(e) )
#         logger.error('Error Processing user preferences, we will set the default user: ' + str(e) )
#         most_similar = 160  # a default user
#
#     print("most_similar:" + str(most_similar))
#     userID = most_similar
#
#     # Get recommendations
#     try:
#         hotels = db.session.query(Hotels.hotelID, Brief_explanations.hotelID, Hotels.name, Hotels.num_reviews,
#                                   Brief_explanations.explanation, Hotels.price, Hotels.stars_file). \
#             outerjoin(Brief_explanations, Hotels.hotelID == Brief_explanations.hotelID). \
#             filter(Brief_explanations.userID == userID).limit(5).all()
#     except Exception as e:
#         logger.error('Error getting recommendations ' + str(e))
#         abort(404)
#
#     return jsonify({'hotels': hotels}), 201

if __name__ == '__main__':
    app.run(debug=True)
