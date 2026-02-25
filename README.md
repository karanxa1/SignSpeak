<div align="center">
  <h1>SignSpeak 🤟</h1>
  <p><b>Real-Time Sign Language Translator & Smart Assistant</b></p>
</div>

SignSpeak is a modern, lightning-fast web application that translates American Sign Language (ASL) into English text and translated Hindi audio in real-time. It uses your computer's webcam to track your hands and machine learning to predict the signs you are making.

This project was built with a rich, premium, minimalistic user interface and an incredibly optimized AI pipeline.

---

## ✨ Features

- **Real-Time Hand Tracking:** Uses Google's MediaPipe to draw skeletal structures over your hands instantly.
- **Machine Learning Inference:** A lightweight TensorFlow Lite model predicts ASL alphabet characters (A-Z) and special actions incredibly fast.
- **Smart Auto-Correction:** As you spell out words, Symmetric Delete spelling correction (SymSpell) predicts what word you are trying to say and offers clickable suggestions.
- **English to Hindi Translation:** With the click of a button, your English sentences are translated to Hindi.
- **Ultra-Realistic Text-to-Speech:** Uses Microsoft Edge Neural TTS engines for lifelike English voices, and Google TTS for flawless Hindi audio playback.
- **Gesture UI Control:** Control the entire app without a keyboard!
  - 👍 **Thumbs Up** = Translate
  - ✌️ **Peace Sign** = Speak
  - 🖐 **Open Palm** = Clear text
- **Dark/Light Mode:** A gorgeous, pure-monochrome aesthetic that supports one-click theme switching.

---

## 🛠 Tech Stack

**Frontend (The UI)**
- **React.js** & **Vite**: For a blazing fast, modern web experience.
- **Tailwind CSS v4**: For the clean, minimalistic, black-and-white styling.
- **WebSockets**: To receive real-time video frames and data from the AI instantly.

**Backend (The AI Engine)**
- **Python & FastAPI**: A hyper-fast modern Python server.
- **MediaPipe**: For mathematical 21-point hand-tracking.
- **TensorFlow Lite**: For running the `.tflite` neural network on your CPU with almost zero lag.
- **OpenCV**: For camera access and frame manipulation.
- **SymSpellPy**: For 1-millisecond word prediction and spelling correction.
- **Deep-Translator & gTTS / Edge-TTS**: For translation and voice synthesis.

---

## 🚀 Ultimate Beginner's Setup Guide

Don't know how to code? Never used Python before? **No problem.** Follow these steps exactly, and you will have SignSpeak running on your computer in 10 minutes.

### Step 1: Install Python (The Backend Engine)
Python is the language that runs the AI. 
1. Go to [Python's official website](https://www.python.org/downloads/).
2. Download **Python 3.10** (or any newer version like 3.11).
3. Open the installer.
4. **CRITICAL STEP FOR WINDOWS USERS:** At the very bottom of the first installation screen, you **MUST** check the box that says **"Add Python to PATH"**. If you don't check this, nothing will work!
5. Click "Install Now" and finish the setup.

### Step 2: Install Node.js (The Frontend Engine)
Node.js is required to run the website interface.
1. Go to [Node.js official website](https://nodejs.org/).
2. Download the **LTS (Long Term Support)** version.
3. Open the installer and click "Next" through all the default options until it finishes.

### Step 3: Download SignSpeak
1. Download this entire folder (`SignSpeak`) to your computer (e.g., to your Downloads or Desktop folder).
2. Open your computer's Terminal:
   - **Mac:** Press `Cmd + Space`, type `Terminal`, and hit Enter.
   - **Windows:** Click the Start menu, type `cmd`, and open the "Command Prompt".

---

### Step 4: Run the App (1-Click Startup!)

We have made it incredibly easy. You do not need to manually configure the frontend or backend! 

**On Mac:**
1. Open the `SignSpeak` folder.
2. Double-click the `run_mac.sh` file.
   *(If double-clicking opens it in an editor, open your Terminal, drag & drop the `run_mac.sh` file into it, and hit Enter).*
3. It will install everything, start the AI server, and open your browser automatically! To close the app, simply press `Ctrl+C` in that terminal.

**On Windows:**
1. Open the `SignSpeak` folder.
2. Double-click the `run_windows.bat` file.
3. Two black command windows will open (one for the AI Backend and one for the Website). The browser will open automatically!
4. To close the app, simply hit the `X` button on those two black windows.

---

### Step 6: Use the App!
1. Open your internet browser (Chrome, Edge, Safari).
2. Type `http://localhost:5173` into the URL bar and hit Enter.
3. The app will ask for **Camera Permissions**. Click **Allow**.
4. You will instantly see your webcam feed and a skeleton mapping your hand!

---

## 🕹 How to use SignSpeak

1. **Making Signs:** Hold your hand up to the camera and make ASL alphabet signs. The app will detect the letter and show the confidence percentage.
2. **Forming Words:** Form letters one by one. The `Backspace` sign deletes a letter. The `Space` sign finishes a word. 
3. **Suggestions:** If you misspell a word, look at the "Suggestions" box. Click the correct word to automatically fix your sentence!
4. **Translation:** Click the black `Translate` button to instantly convert your English sentence to Hindi.
5. **Speech:** Click `Speak Original` to hear an English voice, or `Speak Translation` to hear a pristine Hindi voice read your sentence out loud.
6. **Gesture Control:** Click "Gesture Control" at the top right. Now, you can perform a Thumbs Up to translate, a Peace Sign to speak, or an Open Palm to clear the text, entirely hands-free!

## 🛑 Troubleshooting

- **"The camera feed is black/empty!"**
  Make sure no other app (like Zoom or Skype) is currently using your webcam.
- **"pip is not recognized as an internal or external command" (Windows)**
  You forgot to check the "Add Python to PATH" box in Step 1. Uninstall Python, download it again, and ensure that box is checked!
- **"npm is not recognized"**
  You didn't install Node.js correctly (Step 2). Restart your computer and try again.
- **"The app is laggy"**
  SignSpeak relies on AI running locally on your computer. Make sure your laptop is plugged into power to ensure maximum CPU speed.

---

*Built with ❤️ utilizing FastAPI, React, and TensorFlow Lite.*
