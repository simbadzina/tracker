# Streak Tracker

A beautiful Flask web application that tracks your journey with a visual calendar interface. The app shows your current streak and displays a calendar highlighting all the days you've been strong.

## Features

- **Streak Counter**: Shows your current streak in days
- **Visual Calendar**: Beautiful calendar interface showing your progress
- **Start Date Tracking**: Highlights August 26, 2025 as your start date
- **Responsive Design**: Works on desktop and mobile devices
- **Modern UI**: Clean, motivational interface with gradients and animations

## Installation

1. **Clone or download** this repository to your local machine

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python app.py
   ```

4. **Open your browser** and go to `http://localhost:5000`

## How It Works

- The app automatically calculates your streak from August 26, 2025
- Each day in your streak is highlighted with a green checkmark
- The start date (August 26) is marked with a rocket emoji 🚀
- Today's date is highlighted in blue
- You can navigate between months using the Previous/Next buttons

## Customization

To change the start date, edit the `START_DATE` variable in `app.py`:

```python
START_DATE = date(2025, 8, 26)  # Change this to your start date
```

## Technology Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML5, CSS3, JavaScript
- **Styling**: Custom CSS with gradients and animations
- **Icons**: Font Awesome

## File Structure

```
tracker/
├── app.py              # Main Flask application
├── templates/
│   └── index.html     # Main HTML template
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Motivation

Remember why you started this journey. Every day you stay strong is a victory for your future self. Stay focused, stay disciplined, and keep building the life you deserve.

**"The only way to do great work is to love what you do. Every day is a new beginning."** - Steve Jobs
