from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from .models import User, Test, Response
from . import db, views
import re

regex = re.compile(r'([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+')


def verify_email(email):
    return re.fullmatch(regex, email)


def verify_password(password):
    lower, upper, digit = 0, 0, 0
    for c in password:
        if c.islower():
            lower += 1
        elif c.isupper():
            upper += 1
        elif c.isdigit():
            digit += 1
    return lower >= 1 and upper >= 1 and digit >= 1


auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        if request.form.get('login') == '     Login     ':

            email = request.form.get('email')
            password = request.form.get('password')

            user = User.query.filter_by(email=email).first()

            if user:
                if check_password_hash(user.password, password):
                    flash('Logged in successfully!', category='success')
                    login_user(user, remember=True)
                    return redirect(url_for('views.home'))
                else:
                    flash('Incorrect password!', category='error')
            else:
                flash('Unknown email!', category='error')

        elif request.form.get('createAccount') == 'Create Account':
            return redirect(url_for('.signup'))

        elif request.form.get('takeTest') == 'Take Test':

            studentMail = request.form.get('studentMail')
            testCode = request.form.get('testCode')

            test = Test.query.filter_by(code=testCode).first()

            if not(verify_email(studentMail)):
                flash('Email must be valid!', category='error')
            elif not test:
                flash('Test code unknown!', category='error')
            elif not test.active:
                flash('The test is inactive!', category='error')
            else:
                newResponse = Response()
                newResponse.email = studentMail
                newResponse.start_time = datetime.now()
                db.session.add(newResponse)
                db.session.commit()
                return redirect(url_for('views.takeTest', responseID=newResponse.id, testCode=test.code))

    return render_template("login.html")


@auth.route('/logout')
@login_required
def logout():

    logout_user()
    return redirect(url_for('.login'))


@auth.route('/signup', methods=['GET', 'POST'])
def signup():

    if request.method == 'POST':

        if request.form.get('signUp') == 'Sign Up':

            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            confirmPassword = request.form.get('confirmPassword')

            user = User.query.filter_by(email=email).first()

            if len(name) < 2:
                flash('Name must be greater than 1 characters!', category='error')
            elif not(verify_email(email)):
                flash('Email is not valid!', category='error')
            elif user:
                flash('Email already used!', category='error')
            elif len(password) < 7:
                flash('Password must be greater than 6 characters!', category='error')
            elif not(verify_password(password)):
                flash('Password must contain at least 1 upper uase letter, 1 lower case letter and 1 number!', category='error')
            elif password != confirmPassword:
                flash('Passwords don\'t match!', category='error')
            else:

                new_user = User(name=name, email=email, password=generate_password_hash(password, method='sha256'))

                db.session.add(new_user)
                db.session.commit()
                flash('Account created!', category='success')

                login_user(new_user, remember=True)

                return redirect(url_for('views.home'))

    return render_template("signup.html")
