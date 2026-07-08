# Flight Analytics Assistant - Deployment Guide

## Overview
This is a full-stack application with:
- **Frontend**: Next.js 16 (React 19) with Tailwind CSS
- **Backend**: Python Flask server with Qwen2.5-3B-Instruct LLM
- **Architecture**: RESTful API bridge between frontend and backend

## Prerequisites
- Node.js 18+ (for Next.js frontend)
- Python 3.9+ (for Flask backend)
- 8GB+ RAM (for Qwen2.5-3B-Instruct model)
- GPU recommended (CUDA for faster inference)

## Installation

### 1. Setup Python Backend

```bash
# Navigate to project root
cd /path/to/project

# Create Python environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install flask flask-cors torch transformers huggingface-hub pandas numpy

# Optional: For faster inference with GPU
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 2. Setup Frontend

```bash
# Install Node dependencies (if not already done)
pnpm install  # or npm install / yarn install

# Create .env.local file
cat > .env.local << EOF
NEXT_PUBLIC_API_URL=http://localhost:5000
EOF
```

### 3. Prepare Flight Data

Place your flight CSV file in the project root as `rule_labelled.csv` with columns:
- `timestamp` or `time_seconds`
- `AltMSL` (altitude in feet)
- `IAS` (indicated airspeed in knots)
- `VSpd` (vertical speed in feet/minute)
- `Pitch`, `Roll`, `Heading`
- `GndSpd` (ground speed)
- `Phase` (TAXI, TAKEOFF, CLIMB, CRUISE, DESCENT, APPROACH, LANDING)

Example CSV structure:
```
timestamp,AltMSL,IAS,VSpd,Pitch,Roll,Heading,GndSpd,Phase
2024-01-15 08:00:00,100,0,0,0,0,180,0,TAXI
2024-01-15 08:02:30,150,45,500,8,2,185,50,TAKEOFF
...
```

### 4. Load Model from Hugging Face

The backend will automatically download Qwen2.5-3B-Instruct on first run:

```bash
# Set Hugging Face token (optional, for gated models)
export HF_TOKEN="your_huggingface_token"
```

## Running the Application

### Option A: Development Mode (Separate Terminals)

**Terminal 1 - Backend Server:**
```bash
source venv/bin/activate  # Activate Python environment
python scripts/backend_server.py
# Server starts on http://localhost:5000
```

**Terminal 2 - Frontend Dev Server:**
```bash
pnpm dev
# Frontend starts on http://localhost:3000
```

### Option B: Docker Deployment

Create a `docker-compose.yml`:
```yaml
version: '3.8'

services:
  backend:
    build: ./docker/backend
    ports:
      - "5000:5000"
    volumes:
      - ./:/app
    environment:
      - HF_TOKEN=${HF_TOKEN}
      - FLASK_ENV=production

  frontend:
    build: ./docker/frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:5000
    depends_on:
      - backend
```

Then run:
```bash
docker-compose up
```

## Usage

1. **Open the application**: Navigate to `http://localhost:3000`

2. **Upload Flight Data**:
   - Click "Upload Flight CSV" or drag-drop your CSV file
   - Backend processes and indexes the flight data
   - Confirmation appears when ready

3. **Ask Questions**:
   - Examples:
     - "What was the duration of the taxi?"
     - "Maximum IAS during cruise?"
     - "Summary of takeoff phase"
     - "Any abnormal climb?"
   - System processes with Qwen2.5-3B-Instruct LLM
   - Results show confidence scores and data source

## API Endpoints

### Health Check
```bash
GET /api/health
```

### Upload CSV
```bash
POST /api/upload-csv
Content-Type: multipart/form-data
Body: file (CSV file)
```

### Query Processing
```bash
POST /api/query
Content-Type: application/json
Body: {"query": "What was the taxi duration?"}
```

### Flight Overview
```bash
GET /api/flight-overview
```

### List Phases
```bash
GET /api/phases
```

### Phase Detail
```bash
GET /api/phase/{phase_name}
```

## Configuration

### Backend (scripts/backend_server.py)
- **CSV Path**: Default is `rule_labelled.csv`
- **Port**: Default is 5000
- **Model**: Qwen/Qwen2.5-3B-Instruct
- **Device**: Auto-detects GPU (cuda) or CPU

### Frontend (.env.local)
- **API_URL**: Backend server URL (default: http://localhost:5000)

## Troubleshooting

### Backend Won't Start
```bash
# Check Python installation
python --version  # Should be 3.9+

# Check dependencies
pip list | grep torch transformers

# Test model download
python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('Qwen/Qwen2.5-3B-Instruct')"
```

### API Connection Issues
```bash
# Test backend health
curl http://localhost:5000/api/health

# Check if port 5000 is in use
lsof -i :5000  # On macOS/Linux
netstat -ano | findstr :5000  # On Windows
```

### Model Loading Slow
- First run downloads ~7GB model from Hugging Face
- Subsequent runs use cached model
- GPU significantly speeds up inference

### CSV Upload Fails
- Verify CSV has required columns (at minimum: timestamp, phase, AltMSL, IAS)
- Check file encoding is UTF-8
- Ensure file size < 100MB

## Production Deployment

### Vercel (Frontend)
1. Connect GitHub repo to Vercel
2. Set environment variables in Vercel dashboard:
   - `NEXT_PUBLIC_API_URL=https://your-backend-domain.com`
3. Deploy: Push to main branch

### Backend Options

**Option 1: Railway, Fly.io, or Heroku**
```bash
# Build Docker image
docker build -t flight-analytics-backend .

# Deploy to your hosting service
# (Refer to provider's CLI documentation)
```

**Option 2: AWS EC2/Lambda**
- Use container image
- Set environment variables
- Ensure GPU access (optional)

**Option 3: Self-hosted (VPS)**
```bash
# Install systemd service
sudo cp deployment/flight-analytics.service /etc/systemd/system/
sudo systemctl enable flight-analytics
sudo systemctl start flight-analytics
```

## Performance Optimization

### GPU Acceleration
```bash
# Install CUDA-enabled PyTorch
pip install torch --index-url https://download.pytorch.org/whl/cu118

# Backend will auto-detect and use GPU
```

### Caching
- Install Redis for response caching
- Update backend to cache common queries

### Load Balancing
- Run multiple Flask instances behind Nginx
- Use gunicorn for production:
  ```bash
  pip install gunicorn
  gunicorn -w 4 -b 0.0.0.0:5000 scripts.backend_server:app
  ```

## Support & Documentation

- **LLM Model**: https://huggingface.co/Qwen/Qwen2.5-3B-Instruct
- **Transformers**: https://huggingface.co/docs/transformers
- **Next.js**: https://nextjs.org/docs
- **Flask**: https://flask.palletsprojects.com

## License

This project integrates open-source components. Ensure compliance with:
- Qwen model license
- PyTorch and Transformers licenses
- Next.js and React licenses
