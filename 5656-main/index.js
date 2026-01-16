#!/usr/bin/env node

/**
 * KIE Telegram Bot - Node.js Entry Point
 * This file serves as a wrapper to run the Python bot
 * 
 * Supported platforms:
 * - Render.com (recommended)
 * - Timeweb
 * - Local development
 * 
 * Usage: npm start
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// Load environment variables
require('dotenv').config();

// Check if Python is available
function checkPython() {
  return new Promise((resolve, reject) => {
    const python = spawn('python3', ['--version'], { shell: true });
    let output = '';
    
    python.stdout.on('data', (data) => {
      output += data.toString();
    });
    
    python.stderr.on('data', (data) => {
      output += data.toString();
    });
    
    python.on('close', (code) => {
      if (code === 0 || output.includes('Python')) {
        resolve('python3');
      } else {
        // Try python command
        const python2 = spawn('python', ['--version'], { shell: true });
        python2.on('close', (code2) => {
          if (code2 === 0) {
            resolve('python');
          } else {
            reject(new Error('Python not found. Please install Python 3.8+'));
          }
        });
      }
    });
  });
}

// Check required environment variables
function checkEnv() {
  const required = ['TELEGRAM_BOT_TOKEN', 'KIE_API_KEY'];
  const missing = required.filter(key => !process.env[key]);
  
  if (missing.length > 0) {
    console.error('❌ Missing required environment variables:', missing.join(', '));
    console.error('Please set them in Timeweb interface or .env file');
    process.exit(1);
  }
  
  console.log('✅ Environment variables checked');
}

// Start simple health check server (CRITICAL for Render.com)
function startHealthCheck() {
  const http = require('http');
  const port = process.env.PORT || 10000;
  
  const server = http.createServer((req, res) => {
    if (req.url === '/health' || req.url === '/') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ 
        status: 'ok', 
        service: 'telegram-bot',
        timestamp: new Date().toISOString()
      }));
    } else {
      res.writeHead(404);
      res.end();
    }
  });
  
  server.listen(port, '0.0.0.0', () => {
    console.log(`✅ Health check server started on port ${port}`);
    console.log(`✅ Health check available at http://0.0.0.0:${port}/health`);
    
    // Test health check immediately
    setTimeout(() => {
      const testReq = http.get(`http://localhost:${port}/health`, (testRes) => {
        let data = '';
        testRes.on('data', (chunk) => { data += chunk; });
        testRes.on('end', () => {
          console.log(`✅ Health check test successful: ${data}`);
        });
      });
      testReq.on('error', (err) => {
        console.error(`⚠️  Health check test failed: ${err.message}`);
      });
    }, 100);
  });
  
  server.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
      console.log(`⚠️  Port ${port} already in use (health check may already be running)`);
    } else {
      console.error(`❌ Health check server error: ${err.message}`);
    }
  });
  
  return server;
}

// Start Python bot
async function startBot() {
  console.log('🚀 Starting KIE Telegram Bot...');
  console.log('📦 Using Python version');
  console.log('');
  
  // NOTE: Health check server is already started at the top level
  // This prevents Render.com from killing the process during Python startup
  
  // Check environment
  checkEnv();
  
  // Check Python
  let pythonCmd;
  try {
    pythonCmd = await checkPython();
    console.log(`✅ Python found: ${pythonCmd}`);
  } catch (error) {
    console.error('❌', error.message);
    console.error('');
    console.error('Please install Python 3.8 or higher');
    process.exit(1);
  }
  
  // Check if bot script exists (try bot_kie.py first, then run_bot.py)
  let botScript = path.join(__dirname, 'bot_kie.py');
  if (!fs.existsSync(botScript)) {
    botScript = path.join(__dirname, 'run_bot.py');
    if (!fs.existsSync(botScript)) {
      console.error(`❌ Bot script not found. Tried: bot_kie.py and run_bot.py`);
      console.error(`❌ Current directory: ${__dirname}`);
      console.error(`❌ Files in directory:`, fs.readdirSync(__dirname).filter(f => f.endsWith('.py')).join(', '));
      process.exit(1);
    }
  }
  
  console.log(`📝 Starting bot script: ${botScript}`);
  console.log(`📁 Working directory: ${__dirname}`);
  console.log(`🐍 Python command: ${pythonCmd}`);
  console.log('');
  
  // Spawn Python process with explicit output handling
  // CRITICAL: Use unbuffered output for immediate logging
  const env = {
    ...process.env,
    PYTHONUNBUFFERED: '1', // Force unbuffered output
    PYTHONIOENCODING: 'utf-8' // Ensure UTF-8 encoding
  };
  
  const botProcess = spawn(pythonCmd, ['-u', botScript], { // -u flag for unbuffered
    cwd: __dirname,
    stdio: ['ignore', 'pipe', 'pipe'], // Use pipes to capture output
    shell: true,
    env: env
  });
  
  // Forward stdout to console
  botProcess.stdout.on('data', (data) => {
    const output = data.toString();
    process.stdout.write(output);
    // Force flush
    if (process.stdout.isTTY) {
      process.stdout.write('');
    }
  });
  
  // Forward stderr to console
  botProcess.stderr.on('data', (data) => {
    const output = data.toString();
    process.stderr.write(output);
    // Force flush
    if (process.stderr.isTTY) {
      process.stderr.write('');
    }
  });
  
  // Handle process events
  botProcess.on('error', (error) => {
    console.error('❌ Failed to start bot:', error.message);
    console.error('Error details:', error);
    process.exit(1);
  });
  
  botProcess.on('exit', (code, signal) => {
    if (code !== null) {
      console.log(`\n⚠️  Bot exited with code ${code}`);
      if (code !== 0) {
        console.error('❌ Bot crashed. Check logs above for errors.');
        console.error(`Exit code: ${code}, Signal: ${signal || 'none'}`);
        process.exit(code);
      }
    } else if (signal) {
      console.log(`\n⚠️  Bot terminated by signal: ${signal}`);
      process.exit(1);
    }
  });
  
  // Log that process started
  console.log('✅ Bot process started, waiting for output...');
  console.log('');
  
  // Handle graceful shutdown
  let isShuttingDown = false;
  
  process.on('SIGINT', () => {
    if (isShuttingDown) return;
    isShuttingDown = true;
    console.log('\n🛑 Received SIGINT, shutting down bot gracefully...');
    if (botProcess && !botProcess.killed) {
      botProcess.kill('SIGINT');
      setTimeout(() => {
        if (botProcess && !botProcess.killed) {
          botProcess.kill('SIGTERM');
        }
        setTimeout(() => {
          process.exit(0);
        }, 2000);
      }, 5000);
    } else {
      process.exit(0);
    }
  });
  
  process.on('SIGTERM', () => {
    if (isShuttingDown) return;
    isShuttingDown = true;
    console.log('\n🛑 Received SIGTERM, shutting down bot gracefully...');
    if (botProcess && !botProcess.killed) {
      botProcess.kill('SIGTERM');
      setTimeout(() => {
        if (botProcess && !botProcess.killed) {
          botProcess.kill('SIGKILL');
        }
        setTimeout(() => {
          process.exit(0);
        }, 2000);
      }, 5000);
    } else {
      process.exit(0);
    }
  });
}

// CRITICAL: Start health check server IMMEDIATELY to prevent Render.com SIGTERM
console.log('🏥 Starting health check server FIRST...');
startHealthCheck();

// Give health check server time to bind to port
// CRITICAL: Increase timeout to ensure health check is ready before Render.com checks
setTimeout(() => {
  console.log('✅ Health check server should be responding now');
  console.log('');
  
  // Start the bot
  console.log('='.repeat(60));
  console.log('KIE Telegram Bot - Starting...');
  console.log('='.repeat(60));
  console.log(`Node.js version: ${process.version}`);
  console.log(`Platform: ${process.platform}`);
  console.log(`Working directory: ${__dirname}`);
  console.log(`Process ID: ${process.pid}`);
  console.log('='.repeat(60));
  console.log('');

  // Ensure output is flushed immediately
  process.stdout.setEncoding('utf8');
  process.stderr.setEncoding('utf8');
  
  // Force immediate output flush
  if (process.stdout.isTTY) {
    process.stdout.write('');
  }

  startBot().catch((error) => {
    console.error('❌ Fatal error:', error);
    console.error('Error stack:', error.stack);
    // Don't exit immediately - give health check time to respond
    setTimeout(() => {
      process.exit(1);
    }, 2000);
  });
}, 1000); // Wait 1 second for health check server to start (increased from 500ms)


