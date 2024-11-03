const EMA = require('technicalindicators').EMA


class Indicators {
    constructor() {
        // Wave Trend default parameters
        this.n1 = 10;  // Channel Length
        this.n2 = 21;  // Average Length
        this.obLevel1 = 60;   // Overbought Level 1
        this.obLevel2 = 53;   // Overbought Level 2
        this.osLevel1 = -60;  // Oversold Level 1
        this.osLevel2 = -53;  // Oversold Level 2
    }

    ema(values, period) {
        const k = 2 / (period + 1);
        let emaArray = [];
        emaArray[0] = values[0]; // Start EMA with first value
      
        for (let i = 1; i < values.length; i++) {
          emaArray[i] = values[i] * k + emaArray[i - 1] * (1 - k);
        }
        return emaArray;
    }

    // Calculate EMA (Exponential Moving Average)
    calculateEMA(source, length) {
        const alpha = 2 / (length + 1);
        
        let ema = source[0];
        const results = [ema];
        
        for (let i = 1; i < source.length; i++) {
            ema = alpha * source[i] + (1 - alpha) * ema;
            results.push(ema);
        }
        
        return results;
    }

    // Calculate SMA (Simple Moving Average)
    calculateSMA(data, period) {
        const results = [];
        
        for (let i = data.length - 1; i >= 0; i--) {
            if (i + period > data.length) continue;
            
            let sum = 0;
            for (let j = 0; j < period; j++) {
                sum += data[i + j];
            }
            results.push(sum / period);
        }
        
        return results;
    }

    pineEMA(source, length) {
        const alpha = 2 / (length + 1);
        let sum = source[0];  // Initialize with first value
        const result = new Array(source.length);
        result[0] = sum;
        
        for (let i = 1; i < source.length; i++) {
            sum = alpha * source[i] + (1 - alpha) * sum;
            result[i] = sum;
        }
        
        return result;
    }

    // Calculate Wave Trend
    calculateWaveTrend(candles) {
        if (candles.length < Math.max(this.n1, this.n2, 4)) {
            throw new Error(`Not enough candles to calculate Wave Trend. Need at least ${Math.max(this.n1, this.n2, 4)} candles, but got ${candles.length}`);
        }

        // Ensure candles are in newest-first order
        const orderedCandles = [...candles]; // Now newest-first
        //console.log('orderedCandles', orderedCandles[0]);
        // Step 1: Calculate AP (HLC3) with 8 decimal precision
        const ap = orderedCandles.map(candle => 
            Number(((candle.high + candle.low + candle.close) / 3))
        );

        // Step 2: Calculate ESA = EMA(AP, n1)
        const esa = this.pineEMA(ap, this.n1);

        // Step 3: Calculate D = EMA(abs(AP - ESA), n1)
        const absDiffs = ap.map((value, i) => 
            Number(Math.abs(value - esa[i]))
        );
        //console.log('absDiffs', absDiffs);
        const d = this.pineEMA(absDiffs, this.n1);

        // Step 4: Calculate CI = (AP - ESA) / (0.015 * D)
        const ci = ap.map((value, i) => {
            if (i < esa.length && i < d.length) {
                return Number(((value - esa[i]) / (0.015 * d[i])));
            }
            return 0;
        });

        // Step 5: Calculate TCI = EMA(CI, n2)
        const tci = this.pineEMA({
            period: this.n2,
            values: ci
        });

        // Step 6: Set WT1 = TCI
        const wt1 = tci;

        // Step 7: Calculate WT2 = SMA(WT1, 4)
        let wt2 = [];
        for (let i = 3; i < wt1.length; i++) {
            const sma = Number(((wt1[i] + wt1[i-1] + wt1[i-2] + wt1[i-3]) / 4).toFixed(8));
            wt2.push(sma);
        }

        // Get most recent values
        const currentValues = {
            ap: ap[ap.length - 1],
            esa: esa[esa.length - 1],
            d: d[d.length - 1],
            ci: ci[ci.length - 1],
            tci: tci[tci.length - 1],
            wt1: wt1[wt1.length - 1],
            wt2: wt2[wt2.length - 1]
        };

        // Debug logging for AP and EMA values
        console.log('\nLast 10 candles values:');
        for (let i = 0; i <= 9; i++) {
            const apValue = ap[i];
            const emaValue = esa[i];
            
            // Use the correct timestamp field
            const timestamp = candles[i].timestamp;
            const timeStr = new Date(timestamp).toLocaleTimeString('en-GB', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            
            console.log(`Time: ${timeStr} H: ${candles[i].high?.toFixed(6)} L: ${candles[i].low?.toFixed(6)} C: ${candles[i].close?.toFixed(6)} AP: ${apValue?.toFixed(6)} EMA: ${emaValue?.toFixed(6)} D: ${d[i]}`);
        }

        return {
            ...currentValues,
            overbought1: currentValues.wt1 >= this.obLevel1,
            overbought2: currentValues.wt1 >= this.obLevel2,
            oversold1: currentValues.wt1 <= this.osLevel1,
            oversold2: currentValues.wt1 <= this.osLevel2,
            crossOver: wt1.length > 1 && wt2.length > 1 && 
                (wt1[wt1.length-1] > wt2[wt2.length-1] && wt1[wt1.length-2] <= wt2[wt2.length-2]),
            crossUnder: wt1.length > 1 && wt2.length > 1 && 
                (wt1[wt1.length-1] < wt2[wt2.length-1] && wt1[wt1.length-2] >= wt2[wt2.length-2])
        };
    }

    // Method to calculate Wave Trend for a specific symbol and timeframe
    calculateWaveTrendForSymbol(candleStore, symbol, timeframe) {
        const candles = candleStore[symbol][timeframe];
        if (!candles || candles.length < Math.max(this.n1, this.n2)) {
            throw new Error(`Not enough candles for ${symbol} ${timeframe} to calculate Wave Trend`);
        }
        
        return this.calculateWaveTrend(candles);
    }

    // Method to set custom parameters
    setParameters({
        channelLength = 10,
        averageLength = 21,
        overbought1 = 60,
        overbought2 = 53,
        oversold1 = -60,
        oversold2 = -53
    } = {}) {
        this.n1 = channelLength;
        this.n2 = averageLength;
        this.obLevel1 = overbought1;
        this.obLevel2 = overbought2;
        this.osLevel1 = oversold1;
        this.osLevel2 = oversold2;
    }
}

module.exports = new Indicators();
