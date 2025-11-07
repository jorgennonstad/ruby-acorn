Ah! This is happening because **Ubuntu 23.10+ (or your Python 3.12 installation) enforces PEP 668**, which prevents `pip` from installing packages system-wide in the managed Python environment. That’s why you got the `externally-managed-environment` error.

You have **three safe ways** to install packages:

---

### **1️⃣ Use a Virtual Environment (recommended)**

This keeps your project dependencies isolated and avoids messing with the system Python.

```bash
# Create a virtual environment in your project folder
python3 -m venv venv

# Activate it
source venv/bin/activate

# Now install packages normally
pip install requests
```

Your prompt will change to `(venv)` to show you’re in the virtual environment. When done, you can deactivate with:

```bash
deactivate
```

---

### **2️⃣ Install the system package using apt**

For packages that are available via Ubuntu:

```bash
sudo apt update
sudo apt install python3-requests
```

This works but usually has **older versions** than pip.

---

### **3️⃣ Use pipx (for standalone apps)**

If you want to install a Python application globally without affecting system Python:

```bash
sudo apt install pipx
pipx install requests  # usually for apps, not libraries
```

---

💡 **Best practice for your project**:
Use **a virtual environment** (`python3 -m venv`) for your game server script. This will let you install `requests`, `grafana-api`, and any other dependencies safely.

I can give you a **step-by-step setup command sequence** for your project in Ubuntu that sets up the venv, installs all dependencies, and is ready to run your VM management script. Do you want me to do that?
