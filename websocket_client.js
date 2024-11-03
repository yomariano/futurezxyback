const WebSocket = require('ws');
const axios = require('axios');
const indicators = require('./indicators');

// Configuration
const SYMBOLS = ['INJ_USDT'];
const TIMEFRAMES = ['1m'];
const CANDLE_INTERVALS = {
    '1m': 'Min1',
    '5m': 'Min5',
    '15m': 'Min15'
};

// Data structure to store candles
const candleStore = {};

// Helper function to convert websocket symbol to REST API symbol format
function convertSymbolFormat(symbol, toWebSocket = false) {
    if (toWebSocket) {
        return symbol.replace('_', ''); // BTC_USDT -> BTCUSDT
    }
    return symbol.replace(/([A-Z0-9]+)(USDT)$/, '$1_$2'); // BTCUSDT -> BTC_USDT
}

// Initialize candle store structure
SYMBOLS.forEach(symbol => {
    candleStore[symbol] = {};
    TIMEFRAMES.forEach(timeframe => {
        candleStore[symbol][timeframe] = [];
    });
});

// Fetch historical candles for each symbol and timeframe
async function fetchHistoricalCandles(symbol, timeframe) {
    const apiSymbol = symbol;  // Keep INJ_USDT as is
    const now = Math.floor(Date.now() / 1000);
    const fiveHoursAgo = now - (5 * 60 * 60);
    
    const url = `https://contract.mexc.com/api/v1/contract/kline/${apiSymbol}?interval=Min1&start=${fiveHoursAgo}&end=${now}`;
    
    try {
        console.log('Query:', url);
        const response = await axios.get(url);
        
        // Log the raw response structure
        console.log('Raw response data:', JSON.stringify(response.data, null, 2));
        
        // The response has arrays for each field (time, open, high, low, close, vol)
        const { time, open, high, low, close, vol } = response.data.data;
        
        // Create candles by combining the arrays
        const candles = time.map((t, index) => ({
            timestamp: parseInt(t) * 1000,
            open: parseFloat(open[index]),
            high: parseFloat(high[index]),
            low: parseFloat(low[index]),
            close: parseFloat(close[index]),
            volume: parseFloat(vol[index])
        }));
        
        console.log(`Processed ${candles.length} candles for ${symbol} ${timeframe}`);
        
        // Sort candles by timestamp in descending order (newest first)
        candles.sort((a, b) => b.timestamp - a.timestamp);
        candleStore[symbol][timeframe] = candles;
        
    } catch (error) {
        console.error(`Error fetching historical candles for ${symbol} ${timeframe}:`, error.message);
    }
}

// Add this at the top level, with other declarations
let ws = null;

// Initialize WebSocket connection
function initializeWebSocket() {
    ws = new WebSocket('wss://contract.mexc.com/edge');
    
    ws.onopen = () => {
        console.log('WebSocket connected');
        
        // Send ping every 15 seconds to keep connection alive
        const pingInterval = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ "method": "ping" }));
            }
        }, 15000); // 15 seconds

        // Clear interval on close
        ws.on('close', () => {
            clearInterval(pingInterval);
        });

        SYMBOLS.forEach(pair => {
            // Convert BTC_USDT to BTCUSDT for WebSocket
            //const wsSymbol = pair.replace('_', '');
            const tickerSubscription = {
                "method": "sub.ticker",
                "param": {
                    "symbol": pair
                }
            };
            console.log(`Subscribing to ticker for ${pair}:`, tickerSubscription);
            ws.send(JSON.stringify(tickerSubscription));
        });
    };

    // Update message handling for contract market format
    ws.on('message', (data) => {
        try {
            const message = JSON.parse(data.toString());
            //console.log('Received message:', message);
            
            // Handle pong response if needed
            if (message.channel === "pong") {
                console.log('Received pong:', message.data);
                return;
            }

            if (message.data && message.data.lastPrice) {
                const processedData = {
                    s: message.symbol,  // Use the symbol from the message
                    t: message.data.timestamp,  // Use timestamp from data
                    c: message.data.lastPrice.toString()  // Convert price to string
                };
                updateCandles(processedData);
            }
        } catch (error) {
            console.error('Error processing message:', error);
        }
    });

    // Handle connection errors and reconnect
    ws.on('error', (error) => {
        console.error('WebSocket error:', error);
        setTimeout(initializeWebSocket, 5000);
    });

    ws.on('close', () => {
        console.log('WebSocket disconnected. Reconnecting...');
        setTimeout(initializeWebSocket, 5000);
    });
}

// Update candles with new websocket data
function updateCandles(message) {
    const symbol = message.s;
    const timestamp = parseInt(message.t);
    const price = parseFloat(message.c);
    
    // Debug current state
    console.log('\nWebsocket Update:', {
        time: new Date(timestamp).toLocaleTimeString('en-GB'),
        price: price,
        symbol: symbol
    });

    if (!candleStore[symbol]) {
        console.warn(`Symbol ${symbol} not found in candleStore`);
        return;
    }
    
    TIMEFRAMES.forEach(timeframe => {
        const interval = parseInt(timeframe) * 60 * 1000; // Convert to milliseconds
        const normalizedTimestamp = Math.floor(timestamp / interval) * interval;
        const currentCandle = candleStore[symbol][timeframe][0];
        calculateIndicators(symbol, timeframe);
        // Debug timestamps
        // console.log(`Timeframe ${timeframe}:`, {
        //     messageTime: new Date(timestamp).toLocaleTimeString('en-GB'),
        //     normalizedTime: new Date(normalizedTimestamp).toLocaleTimeString('en-GB'),
        //     currentCandleTime: currentCandle ? new Date(currentCandle.timestamp).toLocaleTimeString('en-GB') : 'none',
        //     price: price
        // });

        if (!currentCandle || normalizedTimestamp > currentCandle.timestamp) {
            // Create new candle
            const newCandle = {
                timestamp: normalizedTimestamp,
                open: price,
                high: price,
                low: price,
                close: price,
                volume: 0
            };
            
            candleStore[symbol][timeframe].unshift(newCandle);
            // console.log('Created new candle:', newCandle);
            
        } else if (normalizedTimestamp === currentCandle.timestamp) {
            // Update existing candle
            const oldValues = { ...currentCandle };
            
            currentCandle.close = price;
            currentCandle.high = Math.max(currentCandle.high, price);
            currentCandle.low = Math.min(currentCandle.low, price);
            
            // console.log('Updated candle:', {
            //     time: new Date(currentCandle.timestamp).toLocaleTimeString('en-GB'),
            //     old: oldValues,
            //     new: { ...currentCandle }
            // });
        }
    });
}

// Function to calculate indicators
function calculateIndicators(symbol, timeframe) {
    try {
        const waveTrend = indicators.calculateWaveTrendForSymbol(candleStore, symbol, timeframe);
        // Get the most recent values (index 0)
        const currentWaveTrend = waveTrend[0];
        
        // Log the Wave Trend values
        // console.log(`${symbol} ${timeframe} - Wave Trend Values:`, {
        //     wt1: currentWaveTrend.wt1.toFixed(2),
        //     wt2: currentWaveTrend.wt2.toFixed(2),
        //     timestamp: new Date(candleStore[symbol][timeframe][0].timestamp).toISOString()
        // });
        
        // Keep the signal logging
        // if (currentWaveTrend.crossOver) {
        //     console.log(`${symbol} ${timeframe}: Wave Trend Bullish Cross`);
        // } else if (currentWaveTrend.crossUnder) {
        //     console.log(`${symbol} ${timeframe}: Wave Trend Bearish Cross`);
        // }
        
        // if (currentWaveTrend.overbought1) {
        //     console.log(`${symbol} ${timeframe}: Strongly Overbought`);
        // } else if (currentWaveTrend.oversold1) {
        //     console.log(`${symbol} ${timeframe}: Strongly Oversold`);
        // }
        
        return waveTrend;
    } catch (error) {
        console.error(`Error calculating indicators for ${symbol} ${timeframe}:`, error.message);
        return null;
    }
}

// Main function to start the application
async function main() {
    // Fetch historical data for all symbols and timeframes
    for (const symbol of SYMBOLS) {
        for (const timeframe of TIMEFRAMES) {
            await fetchHistoricalCandles(symbol, timeframe);
        }
    }
    
    // Initialize WebSocket connection
    initializeWebSocket();
    
    // Now ws is accessible here
    setInterval(() => {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            console.log('WebSocket not connected. Attempting to reconnect...');
            initializeWebSocket();
        }
    }, 30000);
}

// Start the application
main().catch(console.error);
