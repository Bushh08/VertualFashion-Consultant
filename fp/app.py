import csv
from flask import Flask, render_template, Response, url_for
import cv2
import numpy as np
from sklearn.cluster import KMeans
from flask import Flask, render_template, request, redirect, url_for, session, flash

from urllib.parse import urlparse, urljoin
import csv
import os
from datetime import datetime
from flask import Flask, request, jsonify, render_template
import secrets


app = Flask(__name__)

# OpenCV Face Detector
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Skin Tone Color Recommendations
color_suggestions = {
    "Very Fair": ["Soft Pink", "Sky Blue", "Lavender", "Light Gray","Ruby Red","Black","Charcoal","White","Lavender"],
    "Fair": ["Peach", "Coral", "Pastel Yellow", "Mint Green","Brown","Burgundy","Olive","Navy Blue"],
    "Light Medium": ["Rose", "Beige", "Olive", "Warm Blue","salmon Pink","Warm Peach","Terracotta","Mocha","Camel","Rose pink","Mint","Soft Gray"],
    "Medium": ["Olive Green", "Deep Red", "Teal", "Plum","Peach","Olive Green","Brunt Orange","Ruby Red","Cream","Charcoal Gray"],
    "Tan": ["White","Sky Blue","Burnt Orange", "Deep Green", "Burgundy", "Copper"," Gray","Chocolate Brown"],
    "Dark": ["Gold", "Royal Blue", "Rich Green", "Dark Purple","Ruby Red","Burnt orange","Hot Pink","Turqoise"]
}

def detect_skin_tone(face_roi):
    """Detects dominant skin tone from the face region using K-Means clustering."""
    try:
        face_roi = cv2.resize(face_roi, (50, 50))  # Resize to speed up processing
        lab = cv2.cvtColor(face_roi, cv2.COLOR_BGR2LAB)
        pixels = lab.reshape((-1, 3))

        # Apply K-Means Clustering
        kmeans = KMeans(n_clusters=1, random_state=0, n_init=10)
        kmeans.fit(pixels)
        dominant_color = np.uint8(kmeans.cluster_centers_[0])

        return classify_skin_tone(dominant_color)
    except Exception as e:
        print(f"Error in detecting skin tone: {e}")
        return "Unknown"

def classify_skin_tone(lab_color):
    """Classifies skin tone based on LAB values (L: Lightness)."""
    L, A, B = lab_color

    if L > 210:
        return "Very Fair"
    elif 190 < L <= 210:
        return "Fair"
    elif 170 < L <= 190:
        return "Light Medium"
    elif 140 < L <= 170:
        return "Medium"
    elif 100 < L <= 140:
        return "Tan"
    else:
        return "Dark"

def get_clothing_recommendations(skin_tone):
    """Reads the clothing suggestions from a CSV file based on skin tone."""
    clothing_recommendations = []
    try:
        # Open CSV file and read the clothing suggestions
        with open('clothing_recommendations.csv', mode='r') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                # Check if the clothing item matches the skin tone
                if row['skin_tone'] == skin_tone:
                    clothing_recommendations.append({
                        'name': row['clothing_name'],
                        'image_url': row['clothing_image_url'],
                        'category': row['category'],
                        'id': row['clothing_name'].replace(" ", "_")  # Generate a unique ID for each item
                    })
    except Exception as e:
        print(f"Error reading clothing recommendations: {e}")
    
    return clothing_recommendations

# Initialize the camera
camera = cv2.VideoCapture(0)
camera.set(3, 320)  # Width 320px
camera.set(4, 240)  # Height 240px

def generate_frames():
    global last_skin_tone
    while True:
        success, frame = camera.read()
        if not success:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            face_roi = frame[y:y+h, x:x+w]
            if face_roi.size > 0:
                skin_tone = detect_skin_tone(face_roi)
                last_skin_tone = skin_tone  # Save for recommendation later

        _, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    """Renders the homepage with the video feed."""
    return render_template('index.html')

@app.route('/color_analysis')
def color_analysis():
    """Renders the homepage with the video feed."""
    return render_template('color_analysis.html')


@app.route('/recommendation')
def recommendation():
    global last_skin_tone
    skin_tone = last_skin_tone
    colors = color_suggestions.get(skin_tone, ["No color suggestions"])

    # Get clothing recommendations based on skin tone
    clothes = get_clothing_recommendations(skin_tone)

    return render_template('recommendation.html', skin_tone=skin_tone, colors=colors, clothes=clothes)

@app.route('/clothing_detail/<item_id>')
def clothing_detail(item_id):
    clothing_item = None
    all_items = []
    # Load everything once
    with open('clothing_recommendations.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            all_items.append(row)
            if row['clothing_name'].replace(" ", "_") == item_id:
                clothing_item = row

    if not clothing_item:
        return "Item not found", 404

    # Find “similar” by matching category (you can swap in style/fabric/etc.)
    similar_items = [
        row for row in all_items
        if row['category'] == clothing_item['category']
           and row['clothing_name'] != clothing_item['clothing_name']
    ][:8]  # limit to 4 cards

    return render_template(
        'clothing_detail.html',
        clothing_item=clothing_item,
        similar_items=similar_items
    )

@app.route('/video_feed')
def video_feed():
    """Streams the webcam feed to the frontend."""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


app.secret_key = secrets.token_hex(16)  

# Initialize empty lists to represent cart and wishlist
cart = []
wishlist = []


@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'username' not in session:
        flash("You must be logged in to add items to your cart.", "warning")
        return redirect(url_for('login'))
  # 👈 Redirect to login page

    cart = session.get('cart', [])

    price_str = request.form['price'].replace(',', '')  # Remove commas
    item = {
        'name': request.form['name'],
        'price': float(price_str),
        'image_url': request.form['image_url'],
        'description': request.form['description'],
        'category': request.form['category']
    }

    cart.append(item)
    session['cart'] = cart
    session.modified = True
    flash("Item added to cart!", "success")
    return redirect(url_for('cart_page'))




@app.route('/cart')
def cart_page():
    if 'username' not in session:
        flash("Please log in to view your cart.", "warning")
        return redirect(url_for('login'))



    cart = session.get('cart', [])
    total = sum(item['price'] for item in cart)
    return render_template('cart.html', cart=cart, total=total)



@app.route('/remove_from_cart/<int:index>', methods=['POST'])
def remove_from_cart(index):
    cart = session.get('cart', [])
    if 0 <= index < len(cart):
        del cart[index]
        session['cart'] = cart
        session.modified = True
        flash("Item removed from cart.", "info")
    return redirect(url_for('cart_page'))

@app.route('/remove_from_wishlist', methods=['POST'])
def remove_from_wishlist():
    """Removes an item from the wishlist by name."""
    name_to_remove = request.form.get('name')
    wishlist = session.get('wishlist', [])
    
    # Remove item with matching name
    wishlist = [item for item in wishlist if item.get('name') != name_to_remove]
    session['wishlist'] = wishlist
    session.modified = True

    flash("Item removed from wishlist.", "info")
    return redirect(url_for('wishlist_page'))



@app.route('/add_to_wishlist', methods=['POST'])
def add_to_wishlist():
    """Adds an item to the wishlist."""
    if request.method == 'POST':
        item = {
            'name': request.form['name'],
            'price': request.form['price'],
            'image_url': request.form['image_url'],
            'description': request.form['description'],
            'category': request.form['category']
        }

        # Add the item to the wishlist
        wishlist = session.get('wishlist', [])
        wishlist.append(item)
        session['wishlist'] = wishlist
        flash("Item added to wishlist!", "success")
        return redirect(url_for('wishlist_page'))



@app.route('/wishlist')
def wishlist_page():
    """Displays the wishlist page."""
    # Get the wishlist from the session
    wishlist = session.get('wishlist', [])
    return render_template('wishlist.html', wishlist=wishlist)


users = {}

app.secret_key = secrets.token_hex(16)  # Set the secret key for session management
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm = request.form['confirm']

        # Check if user already exists
        try:
            with open('users.csv', 'r') as file:
                reader = csv.reader(file)
                for row in reader:
                    if row and row[0] == username:
                        flash("Username already exists.", "danger")
                        return redirect(request.referrer or url_for('signup'))
        except FileNotFoundError:
            pass  # First user being created

        if password != confirm:
            flash("Passwords do not match.", "danger")
        else:
            with open('users.csv', 'a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([username, password])
            flash("Account created successfully! You can now log in.", "success")
            return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        next_url = request.form.get('next') or url_for('index')

        # Fix: if coming from signup, go to index instead
        if '/signup' in next_url:
            next_url = url_for('index')

        try:
            with open('users.csv', 'r') as file:
                reader = csv.reader(file)
                for row in reader:
                    if row and row[0] == username and row[1] == password:
                        session['username'] = username
                        flash('Logged in successfully.', 'success')
                        return redirect(next_url)
        except FileNotFoundError:
            flash('No user records found. Please sign up first.', 'danger')
            return redirect(url_for('signup'))

        flash('Invalid username or password.', 'danger')
        return redirect(url_for('login', next=next_url))

    # GET method
    next_url = request.args.get('next') or request.referrer or url_for('index')

    # Fix for GET: avoid redirecting back to signup
    if '/signup' in str(next_url):
        next_url = url_for('index')

    return render_template('login.html', next_url=next_url)


@app.route('/logout')
def logout():
    session.pop('username', None)
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(request.referrer or url_for('index'))

@app.route('/buy-now', methods=['GET', 'POST'])
def buy_now():
    if 'username' not in session:
        flash("Please log in to proceed with purchase.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Save form data to session
        session['contact'] = {
            'name': request.form['name'],
            'mobile': request.form['mobile'],
            'pincode': request.form['pincode'],
            'address': request.form['address'],
            'town': request.form['town'],
            'city': request.form['city'],
            'state': request.form['state']
        }
        return redirect(url_for('payment'))
    return render_template('buy_now.html')



@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if request.method == 'POST':
        payment_method = request.form['payment_method']
        contact = session.get('contact', {})

        # Get cart information from session
        cart = session.get('cart', [])
        total_amount = sum(item['price'] for item in cart)

        # Generate order ID
        order_id = int(datetime.now().timestamp())

        # CSV writing
        file_exists = os.path.isfile('orders.csv')
        with open('orders.csv', 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            if not file_exists:
                writer.writerow(['OrderID', 'Name', 'Mobile', 'PinCode', 'Address', 'Town', 'City', 'State', 'PaymentMethod', 'ItemName', 'Price', 'Quantity', 'TotalAmount'])
            
            # Write order details for each item in the cart
            for item in cart:
                writer.writerow([
                    order_id,
                    contact.get('name'),
                    contact.get('mobile'),
                    contact.get('pincode'),
                    contact.get('address'),
                    contact.get('town'),
                    contact.get('city'),
                    contact.get('state'),
                    payment_method,
                    item['name'],
                    item['price'],
                    1,  # Assuming 1 item of each type is bought
                    item['price']  # This is the total for this item
                ])

        return f"✅ Order placed successfully using {payment_method}! Order ID: {order_id}"
    
    return render_template('payment.html')




@app.route('/chat')
def chat():
    return render_template('chat.html')


if __name__ == '__main__':
    app.run(debug=True)