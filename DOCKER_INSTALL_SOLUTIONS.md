# Installation Solutions for crunpyroll (Docker and local environments)

This document provides solutions for installing the crunpyroll package when you encounter setuptools/distutils compatibility issues—in **Docker** or in **local environments** (e.g. macOS, venv).

With the current build system (hatchling), a normal `pip install git+https://github.com/Pixel-LH/crunpyroll.git` should work. Use the steps below if you still see distutils-related errors (e.g. when using an older workflow or a custom setup).

## 🐳 Problem Description

When installing crunpyroll from Git, you might see an error like:
```
AssertionError: /usr/local/lib/python3.11/distutils/core.py
```
or (on macOS):
```
AssertionError: /Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/distutils/core.py
```

This can occur in **Docker containers** (e.g. with Python 3.11) or in **local environments** (macOS with Framework Python, venv) due to setuptools/distutils compatibility issues in pip’s isolated build environment.

## 🔧 Solutions

### Local install (macOS / venv) with distutils error

If you see the same `AssertionError: .../distutils/core.py` on **local macOS** or inside a **venv**, use the same steps as **Solution 2** below: upgrade pip, install setuptools and wheel, then run:

```bash
pip install --no-build-isolation git+https://github.com/Pixel-LH/crunpyroll.git
```

### Solution 1: Automated Installation Script (Recommended)

Use our Docker-compatible installation script:

```bash
# Download and run the installation script
curl -O https://raw.githubusercontent.com/Pixel-LH/crunpyroll/main/install_docker.py
python install_docker.py
```

### Solution 2: Manual Setuptools Management

```bash
# Step 1: Upgrade pip and install compatible setuptools
pip install --upgrade pip
pip install "setuptools>=61.0,<70.0" "wheel>=0.37.0"

# Step 2: Install with PEP 517 and no build isolation
pip install --use-pep517 --no-build-isolation git+https://github.com/Pixel-LH/crunpyroll
```

### Solution 3: Legacy Setup.py Method

```bash
# Use the legacy setup.py installation method
pip install --no-use-pep517 git+https://github.com/Pixel-LH/crunpyroll
```

### Solution 4: Force Reinstall with No Cache

```bash
# Clear cache and force reinstall
pip install --force-reinstall --no-cache-dir git+https://github.com/Pixel-LH/crunpyroll
```

### Solution 5: Dockerfile Integration

Add this to your Dockerfile:

```dockerfile
# Install build dependencies
RUN pip install --upgrade pip "setuptools>=61.0,<70.0" "wheel>=0.37.0"

# Install crunpyroll with specific method
RUN pip install --use-pep517 --no-build-isolation git+https://github.com/Pixel-LH/crunpyroll

# Verify installation
RUN python -c "import crunpyroll; print('✅ crunpyroll installed successfully')"
```

## 🧪 Testing Your Installation

After installation, verify it works:

```python
import crunpyroll
print("✅ crunpyroll imported successfully")

# Check version and basic functionality
client = crunpyroll.Client(email="test", password="test")
print("✅ Client created successfully")
```

## 🐛 Troubleshooting

### Issue: "pip_system_certs: ERROR: truststore not available"
This is a warning and can be safely ignored. It doesn't affect the installation.

### Issue: "Building 'crunpyroll' using the legacy setup.py bdist_wheel mechanism"
This is a deprecation warning when using `--no-use-pep517`. The package will still install correctly.

### Issue: Still getting distutils errors
Try this sequence:
```bash
pip uninstall setuptools -y
pip install "setuptools>=61.0,<70.0"
pip install --use-pep517 --no-build-isolation git+https://github.com/Pixel-LH/crunpyroll
```

## 📋 Environment Requirements

- Python 3.7+
- pip 21.0+
- setuptools 61.0+ (but <70.0 for compatibility)
- wheel 0.37.0+

## 🔍 Technical Details

The issue occurs because:
1. Docker containers may have different setuptools versions
2. The `_distutils_hack` module fails to properly override distutils
3. Build isolation can cause version conflicts

Our solutions address these by:
- Constraining setuptools to compatible versions
- Using appropriate pip flags for the environment
- Providing fallback installation methods

## 📞 Support

If none of these solutions work, please:
1. Check your Python and pip versions
2. Try the automated installation script
3. Report the issue with your environment details
