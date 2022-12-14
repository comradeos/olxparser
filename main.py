from flask import Flask, render_template, url_for, redirect, request, session
from flask_sqlalchemy import SQLAlchemy
from bs4 import BeautifulSoup
from threading import Thread
from time import sleep
import requests


# приложение, настройки, база данных
app = Flask(__name__)
app.config['SECRET_KEY'] = 'MY_SECRET_KEY'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
db = SQLAlchemy(app)


class Users(db.Model):
    '''Модель пользователя
    '''
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    access_level = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f'Users: {self.id}, {self.login}, {self.password}'


class Advertisements(db.Model):
    '''Модель объявления
    '''
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    photo = db.Column(db.String(255), nullable=False)
    seller_name = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f'Users: {self.id}, {self.title}, {self.price}'


HOST = 'https://www.olx.ua'
# заголовки для запросов
HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36',
}


def collect_adv_data(adv:str):
    '''Сбор данных объявления
    '''
    try:
        adv_html = requests.get(url=adv['url'], headers=HEADERS).text
        adv_parsed = BeautifulSoup(adv_html, 'html.parser')
        
        adv_title = adv_parsed.find('h1', class_='css-r9zjja-Text eu5v0x0').get_text()
        adv_author = adv_parsed.find('h4', class_='css-1rbjef7-Text eu5v0x0').get_text()
        adv_image = adv_parsed.find('img', class_='css-1bmvjcs').get('src')
        adv_price = adv['uah_price']
        
        new_item = Advertisements(title=adv_title, price=adv_price,
                                    photo=adv_image, seller_name=adv_author)
        if Advertisements.query.filter_by(photo=new_item.photo).count() == 0:
            db.session.add(new_item)
            db.session.commit()
    except:
        print('>>> error: collect_adv_data')
        pass
    


def crawl_adv_links(item:BeautifulSoup, uah_price:int, adv_urls_list:list):
    '''Сбор данных и запись в базу
    '''
    try:
        href = HOST + item.find('a', class_='css-1bbgabe').get('href')
        if not href in adv_urls_list:
            url_data = {
                'url': href,
                'uah_price': uah_price,
            }
            adv_urls_list.append(url_data)
            collect_adv_data(url_data)
    except:
        print('>>> error: collect_adv_links')
        pass



def parse_olx_data(goal):
    '''Основной фоновый процесс сбора данных и записи в базу
    '''
    page = 1
    adv_urls_list =[]
    while len(adv_urls_list) < goal:
        url = 'https://www.olx.ua/d/uk/hobbi-otdyh-i-sport/muzykalnye-instrumenty/?page=' + str(page)
        html = requests.get(url=url, headers=HEADERS).text
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.find_all('div', class_='css-19ucd76')
        
        threads_items = []
        for item in items:
            try:
                price = int(item.find('p', class_='css-wpfvmn-Text eu5v0x0').
                            get_text().replace('грн.', '').replace(' ',''))
            except:
                price = None
            if price:
                thread = Thread(target=crawl_adv_links, args=[item, price, adv_urls_list], daemon=True)
                threads_items.append(thread)
                thread.start()
        for thread in threads_items:
            thread.join()
            
        page += 1



@app.route('/', methods=['GET', 'POST'])
def index():
    '''Обработка содержимого домашней страницы
    '''
    try:
        user_id = session['user_id']
    except:
        return redirect(url_for('login'))
    
    user = Users.query.get(user_id)
    
    if user.access_level == 1:
        goal = 100
        estimate_time = 10
    elif user.access_level == 2:
        goal = 200
        estimate_time = 20
    elif user.access_level == 3:
        goal = 300
        estimate_time = 30
    else:
        goal = 0
    
    if request.args.get('user') == 'logout':
        del session['user_id']
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        
        if request.form['action'] == "Удалить":
            try:
                item = Advertisements.query.get(request.form['id'])
                db.session.delete(item)
                db.session.commit()
            except:
                pass
            
        if request.form['action'] == "Обновить":
            thread = Thread(target=parse_olx_data, args=[goal], daemon=True)
            thread.start()
            sleep(3)
            return redirect(url_for('index'))


    advertisements = Advertisements.query.order_by(Advertisements.id.asc()).limit(goal).all()
    
    if request.args.get('sort') == 'price_down':
        advertisements.sort(key=lambda x: x.price, reverse=True)
    if request.args.get('sort') == 'price_up':
        advertisements.sort(key=lambda x: x.price, reverse=False)
        
    if request.args.get('data') == 'clear':
        try:
            db.session.query(Advertisements).delete()
            db.session.commit()
            return redirect(url_for('index'))
        except:
            pass

    data = {
        'user_id': user_id,
        'user_login': Users.query.get(user_id).login,
        'user_access_level': Users.query.get(user_id).access_level,
        'advertisements': advertisements,
        'estimate_time': estimate_time,
    }
    
    return render_template('main.html', data=data)



@app.route('/login', methods=['GET', 'POST'])
def login():
    '''Обработка страницы авторизации пользователя
    '''
    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']
        try:
            id = Users.query.filter_by(login=login,password=password).first().id
            session['user_id'] = id
            return redirect(url_for('index'))
        except:
            return render_template('login.html')
    return render_template('login.html')



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port='5000')
