#!/bin/bash

# Diagnostic script for gi module issues on DGX Spark
# Run this to understand what's wrong

echo "🔍 Diagnosing gi Module Issues"
echo "=============================="

echo "1️⃣ System Information:"
echo "Ubuntu version: $(lsb_release -rs)"
echo "Python version: $(python3 --version)"
echo "Python path: $(which python3)"
echo ""

echo "2️⃣ Checking installed packages:"
echo "python3-gi: $(dpkg -l | grep python3-gi || echo 'NOT INSTALLED')"
echo "python3-gi-cairo: $(dpkg -l | grep python3-gi-cairo || echo 'NOT INSTALLED')"
echo "gir1.2-gstreamer-1.0: $(dpkg -l | grep gir1.2-gstreamer-1.0 || echo 'NOT INSTALLED')"
echo ""

echo "3️⃣ Checking Python modules:"
python3 -c "
import sys
print(f'Python executable: {sys.executable}')
print(f'Python path: {sys.path}')
print('')

try:
    import gi
    print('✅ gi module found')
    print(f'gi module location: {gi.__file__}')
except ImportError as e:
    print(f'❌ gi module not found: {e}')
except Exception as e:
    print(f'❌ Error importing gi: {e}')
"

echo ""
echo "4️⃣ Checking GStreamer:"
which gst-launch-1.0 || echo "❌ gst-launch-1.0 not found"
gst-launch-1.0 --version || echo "❌ GStreamer not working"

echo ""
echo "5️⃣ Checking environment variables:"
echo "PYTHONPATH: ${PYTHONPATH:-'Not set'}"
echo "GI_TYPELIB_PATH: ${GI_TYPELIB_PATH:-'Not set'}"

echo ""
echo "6️⃣ Checking for alternative Python installations:"
ls -la /usr/bin/python* 2>/dev/null || echo "No alternative Python found"

echo ""
echo "=============================="
echo "Diagnosis complete."
echo "=============================="
