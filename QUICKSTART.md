# Flight Analytics Assistant - Quick Start Guide

## 🚀 Get Started in 5 Minutes

### Prerequisites
- Python 3.9+ with pip
- Node.js 18+ with pnpm/npm
- 8GB+ RAM (16GB recommended)
- Optional: NVIDIA GPU for faster inference

### Step 1: Clone and Setup (2 minutes)

```bash
# Navigate to project
cd /path/to/flight-analytics

# Setup Python environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Install Node dependencies (if needed)
pnpm install
```

### Step 2: Get Flight Data (1 minute)

The project includes a sample flight CSV. If you have your own:

```bash
# Place your CSV in the root directory
cp /path/to/your/flight_data.csv ./rule_labelled.csv

# Expected columns:
# timestamp, AltMSL, IAS, VSpd, Pitch, Roll, Heading, GndSpd, Phase
```

### Step 3: Start Backend (1 minute)

```bash
# Activate Python environment (if not already)
source venv/bin/activate

# Start Flask server
python scripts/backend_server.py

# You should see:
# ✓ Flight engine initialized
# ✓ Validation layer initialized
# ✓ LLM model loaded
# ✓ Starting Flask server...
# Server running on http://localhost:5000
```

### Step 4: Start Frontend (1 minute)

```bash
# In a new terminal
cd /path/to/flight-analytics

# Start Next.js dev server
pnpm dev

# You should see:
# ▲ Next.js 16.x
# ✓ Compiled successfully
# Server running on http://localhost:3000
```

### Step 5: Use the App

1. **Open browser**: `http://localhost:3000`
2. **Upload flight CSV**: Drag-drop or click to upload
3. **Ask questions**:
   - "What was the taxi duration?"
   - "Maximum IAS during cruise?"
   - "Tell me about the climb phase"
   - "Any abnormal climb?"

Done! 🎉

## 📊 Example Queries

Try these natural language questions:

**Flight Overview:**
- "What are the flight phases?"
- "How long was this flight?"
- "What was the maximum altitude?"

**Phase Analysis:**
- "How long was the taxi?"
- "Tell me about the takeoff"
- "Summary of the cruise phase"
- "What happened during descent?"

**Metrics:**
- "Maximum IAS?"
- "Average speed during climb?"
- "Peak vertical speed?"
- "What was the pitch at landing?"

**Anomalies:**
- "Any abnormal climb?"
- "Were there any unusual g-loads?"
- "Pitch angles out of normal range?"

## 🔍 Verify Integration

### Check Backend Health
```bash
curl http://localhost:5000/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "components": {
    "engine": true,
    "validator": true,
    "llm": true
  }
}
```

### Check Frontend Connection
Open browser dev tools (F12) → Console
Should see no CORS or connection errors

## ⚙️ Configuration

### Change API URL
Edit `.env.local`:
```
NEXT_PUBLIC_API_URL=http://your-backend-url:5000
```

### Change LLM Model
Edit `lib/llm_router.py`:
```python
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"  # Larger model
# or
MODEL_NAME = "Mistral/Mistral-7B"  # Different model
```

### Use GPU
```bash
# Install GPU-enabled PyTorch
pip install torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/cu118

# Backend auto-detects GPU and uses it
```

## 🐛 Troubleshooting

### "Module not found: transformers"
```bash
pip install -r requirements.txt
```

### "Backend not responding"
```bash
# Make sure backend is running
python scripts/backend_server.py

# Check it's accessible
curl http://localhost:5000/api/health
```

### "CORS error in browser console"
- Ensure `NEXT_PUBLIC_API_URL` matches backend URL
- Backend runs on 5000, frontend on 3000

### "Model download takes forever"
- First run downloads ~7GB
- Check internet connection
- Use `HF_TOKEN` if quota-limited

### "Out of memory error"
- Run on system with 8GB+ RAM
- Close other applications
- Try smaller model: `Qwen/Qwen2.5-1.5B`

## 📚 Next Steps

1. **Custom CSV**: Replace `rule_labelled.csv` with your flight data
2. **Production**: See `DEPLOYMENT.md` for hosting options
3. **Fine-tuning**: See `INTEGRATION_GUIDE.md` for advanced features
4. **Customization**: Edit components in `components/` for UI changes

## 🎯 Key Features

- ✅ Natural language flight data queries
- ✅ Qwen2.5-3B-Instruct LLM integration
- ✅ Multi-layer validation preventing hallucinations
- ✅ Confidence scoring on every answer
- ✅ Aviation standards compliance checking
- ✅ Full data traceability and transparency
- ✅ CSV upload and processing
- ✅ Real-time response streaming

## 📖 Documentation

- **Detailed Integration**: See `INTEGRATION_GUIDE.md`
- **Deployment Guide**: See `DEPLOYMENT.md`
- **API Reference**: See comments in `scripts/backend_server.py`
- **Architecture**: See `INTEGRATION_GUIDE.md` → Architecture Overview

## 💡 Tips

**For Better Results:**
- Use clean, well-structured CSV data
- Ensure Phase column has standard values (TAXI, TAKEOFF, etc.)
- Provide complete flight records with all columns
- Use specific metric names (IAS, altitude, pitch, etc.)

**Performance:**
- GPU recommended for production use
- First query loads model (~10s), subsequent queries faster
- Use caching for repeated queries (see future enhancements)

**Development:**
- Backend logs all query processing steps
- Check browser console for frontend errors
- Use `curl` to test API endpoints directly

## 🆘 Need Help?

1. Check error messages in terminal/browser console
2. Review `INTEGRATION_GUIDE.md` for technical details
3. Verify all dependencies installed: `pip list`
4. Test each component individually using curl

---

**Ready to analyze flight data with AI!** 🛫
