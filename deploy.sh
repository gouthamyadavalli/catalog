#!/bin/bash
# Deployment script for Vercel

echo "🚀 Preparing for Vercel deployment..."

# Ensure public folder is synced with static
echo "📁 Syncing static files..."
cp -r static/* public/

# Check if vercel CLI is installed
if ! command -v vercel &> /dev/null; then
    echo "❌ Vercel CLI not found. Install it with: npm i -g vercel"
    exit 1
fi

echo "📦 Deploying to Vercel..."
vercel --prod

echo "✅ Deployment complete!"

