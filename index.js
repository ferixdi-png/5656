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

// Start Python bot
async function startBot() {
  console.log('🚀 Starting KIE Telegram Bot...');
  console.log('📦 Using Python version');
  console.log('');
  
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
  
  // Check if run_bot.py exists
  const botScript = path.join(__dirname, 'run_bot.py');
  if (!fs.existsSync(botScript)) {
    console.error(`❌ Bot script not found: ${botScript}`);
    process.exit(1);
  }
  
  console.log(`📝 Starting bot script: ${botScript}`);
  console.log(`📁 Working directory: ${__dirname}`);
  console.log(`🐍 Python command: ${pythonCmd}`);
  console.log('');
  
  // Spawn Python process with explicit output handling
  const botProcess = spawn(pythonCmd, [botScript], {
    cwd: __dirname,
    stdio: ['ignore', 'pipe', 'pipe'], // Use pipes to capture output
    shell: true,
    env: process.env
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
  process.on('SIGINT', () => {
    console.log('\n🛑 Shutting down bot...');
    botProcess.kill('SIGINT');
    setTimeout(() => {
      botProcess.kill('SIGTERM');
      process.exit(0);
    }, 5000);
  });
  
  process.on('SIGTERM', () => {
    console.log('\n🛑 Shutting down bot...');
    botProcess.kill('SIGTERM');
    setTimeout(() => {
      process.exit(0);
    }, 5000);
  });
}

// Start the bot
console.log('='.repeat(60));
console.log('KIE Telegram Bot - Starting...');
console.log('='.repeat(60));
console.log(`Node.js version: ${process.version}`);
console.log(`Platform: ${process.platform}`);
console.log(`Working directory: ${__dirname}`);
console.log('='.repeat(60));
console.log('');

// Ensure output is flushed immediately
process.stdout.setEncoding('utf8');
process.stderr.setEncoding('utf8');

startBot().catch((error) => {
  console.error('❌ Fatal error:', error);
  console.error('Error stack:', error.stack);
  process.exit(1);
});


