# File to define routes for possible actions of the app
# Chat functionality is based on example from https://github.com/miguelgrinberg/Flask-SocketIO-Chat

from flask import session, redirect, url_for, render_template, request
from . import main
import flask
from .models import db, Hotels, Brief_explanations, Aspects_hotels, Comments, Preferences, Feature_category, Reviews, Actions
import logging
import flask
from flask import Flask, render_template, session
from flask import request
import pandas as pd
import traceback
from flask import Flask, jsonify
from flask import abort
from flask import make_response
from flask import request
from flask import url_for

logger = logging.getLogger('app')
handler = logging.FileHandler('app.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


@main.route('/', methods=['GET', 'POST'])
def index():
    """Login form to enter a room."""
    form = LoginForm()

    try:
        if request.method != 'POST':
            session['name'] = 'You'  # special case for participants of the study, who will always be announced as "you"
            session['room'] = '1'    # we will always use room 1
            if not flask.globals.session.get("name") is None:  # session already set
                session['hotel'] = request.args.get('hotel', None)  # set only hotel
            else:
                flask.globals.session['hotel'] = request.args.get('hotel', None)
            if not request.args.get('actionslog', None) is None:
                if request.args.get('actionslog', None) == 'a158':  # special code for check actionslog
                    actions = db.session.query(Actions.action_type, Actions.page, Actions.feature, Actions.description,
                                               Actions.date, Actions.userID, Actions.condition, Actions.workerID,
                                               Actions.hotelID, Actions.reviewID). \
                        filter(Actions.back == 0).order_by(desc(Actions.date)).all()
                    return render_template('actionslog.html', actions=actions)
            try:
                # validation initial set of variables
                if (flask.globals.session.get("condition") is None) | (flask.globals.session.get("workerID") is None) | (flask.globals.session.get("userID") is None):
                    if (request.args.get('condition', None) is None) | (request.args.get('workerID', None) is None) | (request.args.get('features', None) is None):
                        return render_template('no_params.html')


                if not request.args.get('book', None) is None: # if user clicked to book hotel
                    if request.args.get('book', None) == 'yes':
                        hotelID=''
                        if not request.args.get('hotelID', None) is None:
                            hotelID = request.args.get('hotelID', None)
                        try:
                            new_action = Actions(page='index', action_type='book', description='',
                                                 userID=flask.globals.session['userID'],
                                                 condition=flask.globals.session['condition'],
                                                 workerID=flask.globals.session['workerID'], hotelID=hotelID)

                            db.session.add(new_action)
                            db.session.commit()
                            db.session.close()
                            return render_template('end_page.html')
                        except Exception as e:
                            db.session.rollback()
                            db.session.close()
                            print('Error logging action index page: ' + str(e) + ', workerID:'+flask.globals.session['workerID'])
                            logger.error('Error logging action index page: ' + str(e) + ', workerID:'+flask.globals.session['workerID'])

                first_in = False
                # set variables in session
                ---------------------
                        flask.globals.session['userID'] = userID
                    else:
                        userID = 160 # a default user
                        flask.globals.session['userID'] = userID
                        logger.info('We havent received features, so, we will set the default user: ' + str(e))

                # log action
                back = 0
                if not request.args.get('back', None) is None: back = 1
                try:
                    new_action = Actions(page='index', action_type='load', description='',
                                        userID=flask.globals.session['userID'], condition=flask.globals.session['condition'],
                                        workerID=flask.globals.session['workerID'], back=back)

                    db.session.add(new_action)
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print('Error logging action index page: ' + str(e) + ', workerID:'+flask.globals.session['workerID'])
                    logger.error('Error logging action index page: ' + str(e) + ', workerID:'+flask.globals.session['workerID'])

                userID=flask.globals.session['userID']

                hotels = db.session.query(Hotels.hotelID, Brief_explanations.hotelID, Hotels.name, Hotels.num_reviews,
                                          Brief_explanations.explanation, Hotels.price, Hotels.stars_file). \
                    outerjoin(Brief_explanations, Hotels.hotelID == Brief_explanations.hotelID). \
                    filter(Brief_explanations.userID == userID).limit(5).all()

                for hotel in hotels:
                    print('Hotel name:'+hotel.name)

                # hotels = session.query(Hotels).all()
                return render_template('index.html', hotels=hotels)

            except Exception as e:

                print('Error loading index page: ' + str(e) + ', workerID:'+flask.globals.session['workerID'])
                logger.error('Error loading index page: ' + str(e) + ', workerID:'+flask.globals.session['workerID'])
                return render_template('error.html')

    except:
        session.rollback()
        print('Error loading index page: ' + str(e) + ', workerID:' + flask.globals.session['workerID'])
        logger.error('Error loading index page: ' + str(e) + ', workerID:' + flask.globals.session['workerID'])
        return render_template('error.html')
    finally:
        print("I will close the session")
        db.session.close()


@main.route('/login', methods=['GET', 'POST'])
def login():
    """Login form to enter a room."""
    form = LoginForm()

    if form.validate_on_submit():
        session['name'] = form.name.data
        session['room'] = form.room.data
        return redirect(url_for('.chat'))
    elif request.method == 'GET':
        form.name.data = session.get('name', '')
        form.room.data = session.get('room', '')
    return render_template('index_chat.html', form=form)

@main.route('/chat')
def chat():
    """Chat room. The user's name and room must be stored in
    the session."""
    name = session.get('name', '')
    room = session.get('room', '')
    if name == '' or room == '':
        return redirect(url_for('.index_html'))
    return render_template('chat.html', name=name, room=room)

@main.route('/hotel_general/<int:hotelID>', methods=['GET', 'POST'])
def hotel_general(hotelID):
    try:
        if request.method != 'POST':
            try:
                #db_session
                hotel_revs = db.session.query(Hotels.hotelID, Reviews.hotelID, Hotels.name, Hotels.num_reviews,
                                              Hotels.stars_file, Hotels.score, Hotels.price,
                                              Reviews.author, Reviews.score, Reviews.review_text). \
                    outerjoin(Reviews, Hotels.hotelID == Reviews.hotelID). \
                    filter(Hotels.hotelID == hotelID).all()
                try:
                    new_action = Actions(page='hotel_general', action_type='load', description='', hotelID=hotelID,
                                         userID=flask.globals.session['userID'],
                                         condition=flask.globals.session['condition'],
                                         workerID=flask.globals.session['workerID'], back=0)

                    db.session.add(new_action)
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print('Error logging action hotel general page: ' + str(e) + ', workerID:'+flask.globals.session['workerID'])
                    logger.error('Error logging action hotel general page: ' + str(e) + ', workerID:'+flask.globals.session['workerID'])


                return render_template('hotel_general.html', hotel_revs=hotel_revs)
            except Exception as e:
                print('Error loading comments page: ' + str(e) + ', workerID:'+flask.globals.session['workerID'])
                traceback.print_exc()
                logger.error('Error loading comments page: ' + str(e) + ', workerID:'+flask.globals.session['workerID'])
                return render_template('error.html')
        return ""
    except:
        session.rollback()
        print('Error loading index page: ' + str(e) + ', workerID:' + flask.globals.session['workerID'])
        logger.error('Error loading index page: ' + str(e) + ', workerID:' + flask.globals.session['workerID'])
        return render_template('error.html')
    finally:
        print("I will close the session")
        db.session.close()




@main.route('/todo/api/v1.0/tasks', methods=['GET'])
def get_tasks():
    #return jsonify({'tasks': tasks})
    return jsonify({'tasks': [make_public_task(task) for task in tasks]})


@main.route('/todo/api/v1.0/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    task = [task for task in tasks if task['id'] == task_id]
    if len(task) == 0:
        abort(404)
    return jsonify({'task': task[0]})

@main.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)

@main.route('/todo/api/v1.0/tasks', methods=['POST'])
def create_task():
    if not request.json or not 'title' in request.json:
        abort(400)
    task = {
        'id': tasks[-1]['id'] + 1,
        'title': request.json['title'],
        'description': request.json.get('description', ""),
        'done': False
    }
    tasks.append(task)
    return jsonify({'task': task}), 201

@main.route('/todo/api/v1.0/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    task = [task for task in tasks if task['id'] == task_id]
    if len(task) == 0:
        abort(404)
    if not request.json:
        abort(400)
    if 'title' in request.json and type(request.json['title']) != unicode:
        abort(400)
    if 'description' in request.json and type(request.json['description']) is not unicode:
        abort(400)
    if 'done' in request.json and type(request.json['done']) is not bool:
        abort(400)
    task[0]['title'] = request.json.get('title', task[0]['title'])
    task[0]['description'] = request.json.get('description', task[0]['description'])
    task[0]['done'] = request.json.get('done', task[0]['done'])
    return jsonify({'task': task[0]})

@main.route('/todo/api/v1.0/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    task = [task for task in tasks if task['id'] == task_id]
    if len(task) == 0:
        abort(404)
    tasks.remove(task[0])
    return jsonify({'result': True})

# instead of returning ids of tasks, we can return the URI that controls the task so that clients get the URIs ready to be used
def make_public_task(task):
    new_task = {}
    for field in task:
        if field == 'id':
            new_task['uri'] = url_for('get_task', task_id=task['id'], _external=True)
        else:
            new_task[field] = task[field]
    return new_task


# Method to obtain recommendations based on user preferences
@main.route('/recommendations/', methods=['GET'])
def get_recommendations():
    if not request.json or not 'pref_1' in request.json:
        abort(400)

        preferences_in = [request.json['pref_1'],request.json['pref_2'], request.json['pref_2'], request.json['pref_3'],
                            request.json['pref_4'], request.json['pref_5']]

    # Infer user with similar preferences to our participant
    try:
        preferences = Preferences.query.all() # get list of users in users pref matrix, if userID and their preferences (0 to 4)

        common_aspects = pd.DataFrame(columns=['userID', 'common'])
        for pref in preferences:
            count_occ = 0
            for i in preferences_in:
                if i in [pref.pref_0, pref.pref_1, pref.pref_2, pref.pref_3, pref.pref_4]: count_occ += 1
            common_aspects = common_aspects.append(pd.DataFrame({'userID': [pref.userID], 'common': [count_occ]}))

        max_occ = common_aspects['common'].max()
        common_aspects = common_aspects[common_aspects.common == max_occ]
        most_similar = 0
        for idx, row in common_aspects.iterrows():
            preferences = Preferences.query.filter(Preferences.userID == row.userID).all()
            if pref.pref_0 == preferences_in[0]:
                most_similar = row.userID  # the one with the same first preference

        if most_similar == 0:
            for idx, row in common_aspects.iterrows():
                if pref.pref_1 == preferences_in[0]:
                    most_similar = row.userID  # the one with the same second preference
        if most_similar == 0:
            most_similar = common_aspects.iloc[0, :].userID  # first of the most commonalities

    except Exception as e:
        print('Error Processing user preferences: ' + str(e) + ', workerID:' + flask.globals.session['workerID'])
        logger.error('Error Processing user preferences, we will set the default user: ' + str(e) + ', workerID:' +
                     flask.globals.session['workerID'])
        most_similar = 160  # a default user

    print("most_similar:" + str(most_similar))
    userID = most_similar

    # Get recommendations
    try:
        hotels = db.session.query(Hotels.hotelID, Brief_explanations.hotelID, Hotels.name, Hotels.num_reviews,
                                  Brief_explanations.explanation, Hotels.price, Hotels.stars_file). \
            outerjoin(Brief_explanations, Hotels.hotelID == Brief_explanations.hotelID). \
            filter(Brief_explanations.userID == userID).limit(5).all()
    except Exception as e:
        logger.error('Error getting recommendations ' + str(e))
        abort(404)

    return jsonify({'hotels': hotels}), 201

