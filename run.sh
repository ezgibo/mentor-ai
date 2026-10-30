#!/bin/bash
cd "$(dirname "$0")"

# Check if GEMINI_API_KEY is still the placeholder
if grep -q "GEMINI_API_KEY=your_api_key_here" .env 2>/dev/null; then
    echo "⚠️  UYARI: .env dosyasında GEMINI_API_KEY henüz ayarlanmamış."
    echo "Lütfen .env dosyasını açıp Google AI Studio'dan aldığınız API anahtarını ekleyin:"
    echo "https://aistudio.google.com/apikey"
    echo ""
fi

echo "🚀 Mentor AI başlatılıyor..."
echo "🌐 Tarayıcınızda açın: http://localhost:8000"
echo ""

uv run uvicorn main:app --app-dir backend --reload --port 8000
