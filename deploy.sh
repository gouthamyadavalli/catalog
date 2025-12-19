#!/bin/bash
# Deployment script for Vercel

echo "🚀 Deploying to Vercel..."

# Check if vercel CLI is installed
if ! command -v vercel &> /dev/null; then
    echo "❌ Vercel CLI not found. Install it with: npm i -g vercel"
    exit 1
fi

vercel --prod

echo "✅ Deployment complete!"
