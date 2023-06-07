from . import db
from flask_login import UserMixin


class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150))
    time = db.Column(db.Integer)
    code = db.Column(db.String(100), unique=True)
    active = db.Column(db.Boolean, default=True)
    questions = db.relationship('Question')
    responses = db.relationship('Response')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(1500))
    type = db.Column(db.String(100))
    points = db.Column(db.Float)
    answer = db.Column(db.String(1000))
    options = db.relationship('Option')
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'))


class Option(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(1000))
    row = db.Column(db.Boolean, default=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'))


class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150))
    first_name = db.Column(db.String(150))
    last_name = db.Column(db.String(150))
    start_time = db.Column(db.DateTime)
    submit_time = db.Column(db.DateTime)
    grade = db.Column(db.Float)
    answers = db.relationship('Answer')
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'))


class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_type = db.Column(db.String(100))
    answer = db.Column(db.String(1000))
    points = db.Column(db.Float)
    comment = db.Column(db.String(1000))
    response_id = db.Column(db.Integer, db.ForeignKey('response.id'))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    tests = db.relationship('Test')
