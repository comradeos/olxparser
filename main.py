from flask import Flask, render_template, url_for, redirect, request, session
from flask_sqlalchemy import SQLAlchemy
from bs4 import BeautifulSoup
import threading
import requests




app = Flask(__name__)
app.config['SECRET_KEY'] = 'MY_SECRET_KEY'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'




db = SQLAlchemy(app)




class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    access_level = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f'Users: {self.id}, {self.login}, {self.password}'




class Advertisements(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    photo = db.Column(db.String(255), nullable=False)
    seller_name = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f'Users: {self.id}, {self.title}, {self.price}'




HOST = 'https://www.olx.ua'
HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36',
}




def get_advertisements_data(results:list, parsed_advertise:list):
    try:
        adv_url = HOST + parsed_advertise.find('a', class_='css-1bbgabe').get('href')
        adv_html = requests.get(url=adv_url, headers=HEADERS).text
        adv_parsed = BeautifulSoup(adv_html, 'html.parser')
        adv_author = adv_parsed.find('h4', class_='css-1rbjef7-Text eu5v0x0').get_text()
        adv_image = adv_parsed.find('img', class_='css-1bmvjcs').get('src')
        results.append(
            {
                'title': parsed_advertise.find('h6', class_='css-v3vynn-Text eu5v0x0').get_text(),
                'url': HOST + parsed_advertise.find('a', class_='css-1bbgabe').get('href'),
                'author': adv_author,
                'price': int(parsed_advertise.find('p', class_='css-wpfvmn-Text eu5v0x0').
                            get_text().replace('грн.', '').replace(' ','')),
                'image': adv_image,
            }
        )
    except:
        pass




def get_advertisements_list(goal):
    result = []
    page = 1
    while len(result) < goal:
        url = 'https://www.olx.ua/d/uk/nedvizhimost/?page=' + str(page)
        html = requests.get(url=url, headers=HEADERS).text
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.find_all('div', class_='css-19ucd76')
        
        threads = []
        
        for item in items:
            thread = threading.Thread(target=get_advertisements_data, args=[result, item])
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()
            
        page += 1
    
    return result




@app.route('/', methods=['GET', 'POST'])
def index():
    try:
        user_id = session['user_id']
    except:
        return redirect(url_for('login'))
    
    user = Users.query.get(user_id)
    
    if request.args.get('user') == 'logout':
        del session['user_id']
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if request.form['action'] == "Обновить":
            
            if user.access_level == 1:
                advertisements = get_advertisements_list(150)
            elif user.access_level == 2:
                advertisements = get_advertisements_list(250)
            elif user.access_level == 3:
                advertisements = get_advertisements_list(350)
            else:
               print('error')
                
            for adv in advertisements:
                try:
                    new_item = Advertisements(title=adv['title'], price=adv['price'], 
                                          photo=adv['image'], seller_name=adv['author'])
                    try:
                        duplicate = Advertisements.query.filter_by(photo=adv['image']).one()
                    except:
                        duplicate = None
                    if not duplicate:
                        db.session.add(new_item)
                        db.session.commit()
                except:
                    print('error')
                    pass
            
        if request.form['action'] == "Удалить":
            try:
                item = Advertisements.query.get(request.form['id'])
                db.session.delete(item)
                db.session.commit()
            except:
                pass
    
    if user.access_level == 1:
        advertisements = Advertisements.query.order_by(Advertisements.id.desc()).limit(100).all()
        estimate_time = 15
        
    elif user.access_level == 2:
        advertisements = Advertisements.query.order_by(Advertisements.id.desc()).limit(200).all()
        estimate_time = 25
        
    elif user.access_level == 3:
        advertisements = Advertisements.query.order_by(Advertisements.id.desc()).limit(300).all()
        estimate_time = 35
        
    else:
        advertisements = []
        estimate_time = 0
    
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
