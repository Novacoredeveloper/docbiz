#!/bin/bash

# Deployment script for DocBiz

echo "Starting DocBiz deployment..."

# Navigate to project directory
cd /home/ozymandius/docbiz/backend

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Run migrations
echo "Running migrations..."
python manage.py migrate

# Create superuser if needed (uncomment if first deployment)
echo "Creating superuser..."
python manage.py createsuperuser

# setup llm services
python manage.py setup_llm_providers

# Set proper permissions
echo "Setting permissions..."
sudo chown -R ozymandius:www-data /home/ozymandius/docbiz/backend
sudo chmod -R 755 /home/ozymandius/docbiz/backend
sudo chmod 664 /home/ozymandius/docbiz/backend/docbiz.sock

# Reload systemd and restart services
echo "Reloading services..."
sudo systemctl daemon-reload
sudo systemctl enable docbiz.service
sudo systemctl restart docbiz.service

# Enable nginx site and reload
sudo ln -sf /etc/nginx/sites-available/docbiz /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

echo "Deployment complete!"
echo "Check service status: sudo systemctl status docbiz.service"
echo "Check nginx status: sudo systemctl status nginx"