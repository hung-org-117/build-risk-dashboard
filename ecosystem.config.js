module.exports = {
  apps: [
    {
      name: 'frontend',
      cwd: './frontend',
      script: 'npm',
      args: 'run start',
      env: {
        NODE_ENV: 'production',
      },
    },
    {
      name: 'backend-api',
      cwd: './backend',
      script: 'uv',
      args: 'run uvicorn app.main:app --host 0.0.0.0 --port 8000',
      interpreter: 'none', // Put 'none' to execute script as binary
    },
    {
      name: 'backend-celery',
      cwd: './backend',
      script: 'uv',
      args: 'run celery -A app.celery_app worker --loglevel=info --pool=threads --concurrency=4',
      interpreter: 'none',
    },
  ],
};
