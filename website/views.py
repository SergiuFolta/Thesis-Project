from datetime import datetime
from flask import flash
from email.message import EmailMessage
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from .models import Test, Question, Option, Response, Answer
import ssl
import smtplib
from . import db
import string
import random
import xlsxwriter
import os


views = Blueprint('views', __name__)


def generateCode():

    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for i in range(15))


def saveTest(test):

    test.title = request.form.get('testName')
    test.time = int(request.form.get('testTime'))

    for index, question in enumerate(test.questions):

        question.text = request.form.get('questionText' + str(index + 1))
        question.type = request.form.get('questionType' + str(index + 1))
        question.points = float(request.form.get('points' + str(index + 1)))

        if question.type in ["multipleChoice", "checkboxes", "dropdown", "matching"]:
            for index2, option in enumerate(question.options):
                option.text = request.form.get('option' + str(index + 1) + str(index2 + 1))
                if question.type == "matching" and request.form.get('row' + str(index + 1) + str(index2 + 1)) == "column":
                    option.row = False
                else:
                    option.row = True
        else:
            question.options.clear()
            for option in question.options:
                db.session.delete(option)

    db.session.commit()


def collectAnswers(response, test):

    response.first_name = request.form.get('firstName')
    response.last_name = request.form.get('lastName')
    response.submit_time = datetime.now()
    response.test_id = test.id

    for index, question in enumerate(test.questions):
        if question.type in ['shortAnswer', 'longAnswer', 'multipleChoice', 'dropdown']:
            response.answers.append(
                Answer(question_type=question.type, answer=request.form.get('answer' + str(index + 1))))
        elif question.type in ['checkboxes', 'matching']:
            response.answers.append(Answer(question_type=question.type, answer=','.join(
                str(element) for element in request.form.getlist('answer' + str(index + 1)))))
        elif question.type == 'fileUpload':
            file = request.files['answer' + str(index + 1)]
            if file.filename != '':
                file.filename = 'response' + str(response.id) + 'answer' + str(index + 1) + '.' + str(
                    file.filename.rsplit('.', 1)[1].lower())
                filename = secure_filename(file.filename)
                response.answers.append(Answer(question_type=question.type, answer=filename))
                file.save(os.path.join("website/static/uploads", filename))
            else:
                response.answers.append(Answer(question_type=question.type, answer='nofile'))

    grade = 0
    for index, answer in enumerate(response.answers):
        if answer.question_type in ['shortAnswer', 'longAnswer', 'multipleChoice',
                                    'dropdown'] and answer.answer == test.questions[index].answer:
            answer.points = test.questions[index].points
        elif answer.question_type in ['checkboxes', 'matching']:
            if answer.answer == test.questions[index].answer:
                answer.points = test.questions[index].points
            elif answer.answer == '' or len(answer.answer.split(',')) == len(test.questions[index].options):
                answer.points = 0
            else:
                answer.points = test.questions[index].points

                if answer.question_type == 'matching':
                    col = 0
                    for option in test.questions[index].options:
                        if not option.row:
                            col += 1
                    errorPoints = test.questions[index].points / ((len(test.questions[index].options)-col)*col)
                else:
                    errorPoints = test.questions[index].points / len(test.questions[index].options)

                for item in test.questions[index].answer.split(','):
                    if item not in answer.answer.split(','):
                        answer.points -= errorPoints

                for item in answer.answer.split(','):
                    if item not in test.questions[index].answer.split(','):
                        answer.points -= errorPoints

                answer.points = round(answer.points, 2)
        else:
            answer.points = 0
        grade += answer.points
    response.grade = grade

    db.session.commit()


def sendEmail(email_receiver, subject, filename):

    email_sender = 'testcreationresults@gmail.com'
    email_password = 'wyhluwbakuhsjsjv'

    em = EmailMessage()
    em['From'] = email_sender
    em['To'] = email_receiver
    em['Subject'] = subject

    text = """\
    Hello! 
    Here are the grades obtained by the students:
    """
    em.set_content(text)

    with open(os.path.join("website/static/uploads", filename), 'rb') as file:
        em.add_attachment(file.read(), maintype='application', subtype='octet-stream', filename='GradesReport.xlsx')

    context = ssl.create_default_context()

    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
        smtp.login(email_sender, email_password)
        smtp.sendmail(email_sender, email_receiver, em.as_string())

    flash('Grades report successfully sent! Please check your email!', category='success')


def sendFeedbackEmail(email_receiver, subject, html, response):

    email_sender = 'testcreationresults@gmail.com'
    email_password = 'wyhluwbakuhsjsjv'

    em = EmailMessage()
    em['From'] = email_sender
    em['To'] = email_receiver
    em['Subject'] = subject

    text = """\
    Hello!
    You can find your graded test attached:
    """

    em.set_content(text)

    pagename = response.first_name + response.last_name + "Response.html"
    with open(os.path.join("website/static/uploads", pagename), 'w') as f:
        f.write(html)
    with open(os.path.join("website/static/uploads", pagename), 'rb') as file:
        em.add_attachment(file.read(), maintype='application', subtype='octet-stream', filename=pagename)

    for id, answer in enumerate(response.answers):
        if answer.question_type == 'fileUpload' and answer.answer != 'nofile':
            filename, file_extension = os.path.splitext(os.path.join("website/static/uploads", answer.answer))
            attachment = 'Answer to Question ' + str(id) + file_extension
            with open(os.path.join("website/static/uploads", answer.answer), 'rb') as file:
                em.add_attachment(file.read(), maintype='application', subtype='octet-stream', filename=attachment)

    context = ssl.create_default_context()

    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
        smtp.login(email_sender, email_password)
        smtp.sendmail(email_sender, email_receiver, em.as_string())

    os.remove(os.path.join("website/static/uploads", pagename))
    flash('Test feedback successfully sent!', category='success')


def createReport(test):

    filename = str(test.id) + "GradeReport.xlsx"

    workbook = xlsxwriter.Workbook(os.path.join("website/static/uploads", filename))
    worksheet = workbook.add_worksheet('Grades')

    row = 0
    col = 0
    for response in test.responses:
        worksheet.write(row, col, response.last_name)
        worksheet.write(row, col + 1, response.first_name)
        worksheet.write(row, col + 2, response.email)
        worksheet.write(row, col + 3, response.grade)
        row += 1

    workbook.close()

    subject = test.title + 'Results'

    sendEmail(current_user.email, subject, filename)

    os.remove(os.path.join("website/static/uploads", filename))


def sendFeedback(response, test):

    checked = []
    for index, question in enumerate(test.questions):
        if question.type in ["multipleChoice", "checkboxes", "dropdown", "matching"] and response.answers[index].answer:
            checked += response.answers[index].answer.split(',')

    subject = response.last_name + ' ' + response.first_name + '\'s results from the ' + test.title
    html = render_template("gradedresponse.html", test=test, response=response, checked=checked)
    emails = [response.email, current_user.email]

    sendFeedbackEmail(emails, subject, html, response)


@views.route('/', methods=['GET', 'POST'])
@login_required
def home():

    if request.method == 'POST':

        for index, test in enumerate(current_user.tests):
            if request.form.get('gradeTest'+str(index+1)):
                return redirect(url_for('.gradeTest', testID=test.id))
            if request.form.get('inactivateTest'+str(index+1)):
                inactivateTest(test.id)
            if request.form.get('activateTest'+str(index+1)):
                activateTest(test.id)
            if request.form.get('deleteTest'+str(index+1)):
                deleteTest(test.id)
            if request.form.get('modifyTest'+str(index+1)):

                return redirect(url_for('.modifyTest', testID=test.id))

        if request.form.get('createTest'):
            newTest = Test()
            db.session.add(newTest)
            db.session.commit()
            return redirect(url_for('.createTest', testID=newTest.id))

        if request.form.get('logout'):
            return redirect(url_for('auth.logout'))

    return render_template("home.html", user=current_user)


@views.route('/createTest', methods=['GET', 'POST'])
@login_required
def createTest():

    test = Test.query.filter_by(id=request.args.get("testID", None)).first()

    if request.method == 'POST':

        if request.form.get('update'):
            saveTest(test)

        for index, question in enumerate(test.questions):
            for index2, option in enumerate(question.options):
                if request.form.get('deleteOption' + str(index + 1) + str(index2 + 1)):
                    question.options.remove(option)
                    db.session.delete(option)
                    db.session.commit()

        for index, question in enumerate(test.questions):
            if question.type in ["multipleChoice", "checkboxes", "dropdown", "matching"] and request.form.get('addOption'+str(index+1)):
                saveTest(test)
                question.options.append(Option(row=True))
                db.session.commit()

        for index, question in enumerate(test.questions):
            if not question.type == request.form.get('questionType'+str(index+1)):
                question.options.clear()
                saveTest(test)
                question.type = request.form.get('questionType'+str(index+1))
                db.session.commit()

        if request.form.get('addQuestion'):
            saveTest(test)
            test.questions.append(Question(type="shortAnswer"))
            db.session.commit()

        for index, question in enumerate(test.questions):
            if request.form.get('delete'+str(index+1)):
                test.questions.remove(question)
                for option in question.options:
                    db.session.delete(option)
                db.session.delete(question)
                db.session.commit()

        if request.form.get('saveTest'):
            code = generateCode()
            while Test.query.filter_by(code=code).first():
                code = generateCode()

            test.code = code
            test.user_id = current_user.id

            saveTest(test)
            db.session.commit()
            return redirect(url_for('.testAnswers', testCode=test.code))

        if request.form.get('cancel'):
            deleteTest(test.id)
            db.session.commit()
            return redirect(url_for('.home'))

    return render_template("createtest.html", user=current_user, test=test)


@views.route('/gradeTest', methods=['GET', 'POST'])
@login_required
def gradeTest():

    test = Test.query.filter_by(id=request.args.get("testID", None)).first()

    if request.method == 'POST':

        for index, response in enumerate(test.responses):
            if request.form.get('gradeResponse'+str(index+1)):
                return redirect(url_for('.gradeResponse', testID=test.id, responseID=response.id))
            if request.form.get('sendFeedback'+str(index+1)):
                sendFeedback(response, test)
            if request.form.get('deleteResponse'+str(index+1)):
                deleteResponse(response.id)

        if request.form.get('gradesReport'):
            createReport(test)

        if request.form.get('home'):
            return redirect(url_for('.home'))

    return render_template("gradetest.html", test=test)


@views.route('/gradeResponse', methods=['GET', 'POST'])
@login_required
def gradeResponse():

    response = Response.query.filter_by(id=request.args.get("responseID", None)).first()
    test = Test.query.filter_by(id=request.args.get("testID", None)).first()

    checked = []
    for index, question in enumerate(test.questions):
        if question.type in ["multipleChoice", "checkboxes", "dropdown", "matching"] and response.answers[index].answer:
            checked += response.answers[index].answer.split(',')

    if request.method == 'POST':

        if request.form.get('finishGrading'):

            grade = 0
            for index, answer in enumerate(response.answers):
                answer.comment = request.form.get('comment'+str(index+1))
                answer.points = float(request.form.get('points'+str(index+1)))
                grade += answer.points

            response.grade = grade
            db.session.commit()

            return redirect(url_for('.gradeTest', testID=test.id))

    return render_template("graderesponse.html", test=test, response=response, checked=checked)


def deleteResponse(response_id):

    response = Response.query.filter_by(id=response_id).first()

    for answer in response.answers:
        if answer.question_type == 'fileUpload' and answer.answer != 'nofile':
            os.remove(os.path.join("website/static/uploads", answer.answer))
        db.session.delete(answer)
    db.session.delete(response)
    db.session.commit()


def inactivateTest(test_id):

    test = Test.query.filter_by(id=test_id).first()
    test.active = False
    db.session.commit()

    return redirect(url_for('.home'))


def activateTest(test_id):

    test = Test.query.filter_by(id=test_id).first()
    test.active = True
    db.session.commit()

    return redirect(url_for('.home'))


@views.route('/modifyTest', methods=['GET', 'POST'])
@login_required
def modifyTest():

    test = Test.query.filter_by(id=request.args.get("testID", None)).first()

    if request.method == 'POST':

        if request.form.get('update'):
            saveTest(test)

        for index, question in enumerate(test.questions):
            for index2, option in enumerate(question.options):
                if request.form.get('deleteOption' + str(index + 1) + str(index2 + 1)):
                    question.options.remove(option)
                    db.session.delete(option)
                    db.session.commit()

        for index, question in enumerate(test.questions):
            if question.type in ["multipleChoice", "checkboxes", "dropdown", "matching"] and request.form.get(
                    'addOption' + str(index + 1)):
                saveTest(test)
                question.options.append(Option(row=True))
                db.session.commit()

        for index, question in enumerate(test.questions):
            if not question.type == request.form.get('questionType' + str(index + 1)):
                question.options.clear()
                saveTest(test)
                question.type = request.form.get('questionType' + str(index + 1))
                db.session.commit()

        if request.form.get('addQuestion'):
            saveTest(test)
            test.questions.append(Question(type="shortAnswer"))
            db.session.commit()

        for index, question in enumerate(test.questions):
            if request.form.get('delete' + str(index + 1)):
                test.questions.remove(question)
                for option in question.options:
                    db.session.delete(option)
                db.session.delete(question)
                db.session.commit()

        if request.form.get('modifyTest'):
            saveTest(test)

            for response in test.responses:
                deleteResponse(response.id)

            db.session.commit()
            return redirect(url_for('.testAnswers', testCode=test.code))

    return render_template("modifytest.html", user=current_user, test=test)


def deleteTest(test_id):

    test = Test.query.filter_by(id=test_id).first()

    for question in test.questions:
        for option in question.options:
            db.session.delete(option)
        db.session.delete(question)

    for response in test.responses:
        deleteResponse(response.id)

    db.session.delete(test)
    db.session.commit()


@views.route('/testAnswers', methods=['GET', 'POST'])
@login_required
def testAnswers():

    test = Test.query.filter_by(code=request.args.get("testCode", None)).first()

    if request.method == 'POST':

        for index, question in enumerate(test.questions):
            if question.type in ['shortAnswer', 'longAnswer', 'multipleChoice', 'dropdown'] and request.form.get('answer' + str(index + 1)) != '':
                question.answer = request.form.get('answer' + str(index + 1))
            elif question.type in ['checkboxes', 'matching'] and request.form.get('answer' + str(index + 1)) != '':
                question.answer = ','.join(str(element) for element in request.form.getlist('answer' + str(index + 1)))

        if request.form.get('submitAnswers'):
            db.session.commit()
            return redirect(url_for('.home'))

    return render_template("testAnswers.html", user=current_user, test=test)


@views.route('/takeTest', methods=['GET', 'POST'])
def takeTest():

    response = Response.query.filter_by(id=request.args.get("responseID", None)).first()
    test = Test.query.filter_by(code=request.args.get("testCode", None)).first()

    points = 0
    for question in test.questions:
        points += question.points

    if request.method == 'POST':

        if request.form.get('submitAnswers'):
            collectAnswers(response, test)
            return redirect(url_for('.preliminaryGrade', responseID=response.id, testCode=test.code))

    return render_template("takeTest.html", test=test, points=points)


@views.route('/preliminaryGrade', methods=['GET', 'POST'])
def preliminaryGrade():

    response = Response.query.filter_by(id=request.args.get("responseID", None)).first()
    test = Test.query.filter_by(code=request.args.get("testCode", None)).first()

    checked = []
    for index, question in enumerate(test.questions):
        if question.type in ["multipleChoice", "checkboxes", "dropdown", "matching"] and response.answers[index].answer:
            checked += response.answers[index].answer.split(',')

    return render_template("preliminaryGrade.html", response=response, test=test, checked=checked)
