# ⚽ FootyFeud

**FootyFeud** is a Wordle-inspired football guessing game built with Streamlit. Players must identify a mystery footballer within six tries using dynamic clues.

## 🚀 Features

* **Daily Challenge**: A synchronized global mystery player that resets every 24 hours.
* **Random Mode**: Practice your skills with unlimited random players.
* **Smart Feedback**:
* 🟩 **Green**: Exact match for Nationality, League, Club, or Position.
* 🟨 **Yellow**: Age is within 2 years of the target.
* ↑/↓ **Arrows**: Indicates if the mystery player is older or younger.


* **Persistence**: Uses Firebase Firestore to save your stats, streaks.

---

## 🛠️ Tech Stack

* **Frontend**: [Streamlit](https://streamlit.io/)
* **Database**: [Google Firebase Firestore](https://firebase.google.com/)
* **Language**: Python 3.9+

---

## 📂 Project Structure

```text
footyfeud/
├── app.py              # Main Streamlit application logic
├── requirements.txt    # Python dependencies
├── src/
│   └── utils.py        # Data loading and helper functions
│   └── auth.py        # Authentication
├── data/
│   └── players.json    # Footballer database
└── .streamlit/
    └── secrets.toml    # (Local only) Firebase credentials

```

---

## ⚙️ Local Setup

1. **Clone the repository**:
```bash
git clone https://github.com/trongtricoder/Footy-Feud.git
cd footyfeud

```


2. **Install dependencies**:
```bash
pip install -r requirements.txt

```


3. **Set up Firebase**:
* Create a project in the [Firebase Console](https://console.firebase.google.com/).
* Generate a **Service Account JSON key**.
* Create a `.streamlit/secrets.toml` file and add your key:


```toml
[firebase]
textkey = ''' { "your": "json_content_here" } '''

```


4. **Run the app**:
```bash
streamlit run app.py

```



---

## 📊 Database Schema

The app expects a `players.json` in the following format:

```json
[
  {
    "name": "Lamine Yamal",
    "nationality": "Spain",
    "league": "La Liga",
    "club": "FC Barcelona",
    "position": "FW",
    "age": 18,
    "img_url": "https://example.com/yamal.png"
  }
]

```

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.

---
