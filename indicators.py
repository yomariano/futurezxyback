import numpy as np
import pandas as pd
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
import logging
from typing import List, Dict, Any
from datetime import datetime
import traceback

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class Indicators:
    def __init__(self):
        self.n1 = 10  # Channel Length
        self.n2 = 21  # Average Length
        self.ob_level1 = 60   # Overbought Level 1
        self.ob_level2 = 53   # Overbought Level 2
        self.os_level1 = -60  # Oversold Level 1
        self.os_level2 = -53  # Oversold Level 2

    def calculate_rsi(self, candles, period=14):
        """Calculate RSI using ta library's RSIIndicator."""
        try:
            # Sort candles by timestamp in ascending order (oldest first)
            sorted_candles = sorted(candles, key=lambda x: x['timestamp'])
            
            # Convert to pandas DataFrame and extract close prices
            df = pd.DataFrame(sorted_candles)
            
            # Ensure we have enough data points
            if len(df) < period + 1:
                logger.warning(f"Not enough data points for RSI calculation. Need {period + 1}, got {len(df)}")
                return pd.Series()
            
            price_series = pd.Series([float(p) for p in df['close']])
            
            # Calculate RSI using ta library
            rsi_indicator = RSIIndicator(
                close=price_series,
                window=period,
                fillna=True
            )
            rsi = rsi_indicator.rsi()
            
            # Debug logging
            logger.debug(f"RSI calculation - Last price: {price_series.iloc[-1]:.2f}, RSI: {rsi.iloc[-1]:.2f}")
            
            return rsi
            
        except Exception as e:
            logger.error(f"Error calculating RSI: {str(e)}")
            logger.error(traceback.format_exc())
            return pd.Series()

    def calculate_wave_trend(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(candles) < max(self.n1, self.n2, 4):
            raise ValueError(f"Not enough candles to calculate Wave Trend. Need at least {max(self.n1, self.n2, 4)} candles, but got {len(candles)}")

        # Sort candles by timestamp in descending order (newest first)
        sorted_candles = sorted(candles, key=lambda x: x['timestamp'], reverse=True)
        
        # Convert sorted candles to pandas DataFrame and reverse order (oldest first)
        df = pd.DataFrame(sorted_candles[::-1])
        
        # Calculate AP (HLC3)
        df['ap'] = (df['high'] + df['low'] + df['close']) / 3
        
        # Calculate ESA = EMA(AP, n1)
        df['esa'] = df['ap'].ewm(span=self.n1, min_periods=self.n1, adjust=False).mean()
        
        # Calculate D = EMA(abs(AP - ESA), n1)
        df['d'] = abs(df['ap'] - df['esa'])
        df['d'] = df['d'].ewm(span=self.n1, min_periods=self.n1, adjust=False).mean()
        
        # Avoid division by zero
        df['d'] = df['d'].replace(0, 0.00001)
        
        # Calculate CI = (AP - ESA) / (0.015 * D)
        df['ci'] = (df['ap'] - df['esa']) / (0.015 * df['d'])
        
        # Calculate WT1 = EMA(CI, n2)
        df['wt1'] = df['ci'].ewm(span=self.n2, min_periods=self.n2, adjust=False).mean()
        
        # Calculate WT2 = SMA(WT1, 4)
        df['wt2'] = df['wt1'].rolling(window=4, min_periods=4).mean()
        
        # Reverse back to newest first
        df = df.iloc[::-1]

        # Debug logging
        #print('\nLast 10 candles values:')
        for i in range(min(10, len(df))):
            timestamp = datetime.fromtimestamp(df.iloc[i]['timestamp'] / 1000).strftime('%H:%M:%S')
            wt2_value = df.iloc[i]['wt2']
            wt2_str = f"{wt2_value:.6f}" if not pd.isna(wt2_value) else "N/A"
            
            # print(f"Time: {timestamp} "
            #       f"H: {df.iloc[i]['high']:.6f} "
            #       f"L: {df.iloc[i]['low']:.6f} "
            #       f"C: {df.iloc[i]['close']:.6f} "
            #       f"AP: {df.iloc[i]['ap']:.6f} "
            #       f"EMA: {df.iloc[i]['esa']:.6f} "
            #       f"D: {df.iloc[i]['d']:.6f} "
            #       f"WT1: {df.iloc[i]['wt1']:.6f} "
            #       f"WT2: {wt2_str}")

        # Get current values
        current = df.iloc[0]
        previous = df.iloc[1] if len(df) > 1 else None

        return {
            'ap': float(current['ap']),
            'esa': float(current['esa']),
            'd': float(current['d']),
            'ci': float(current['ci']),
            'wt1': float(current['wt1']),
            'wt2': float(current['wt2']) if not pd.isna(current['wt2']) else 0.0,
            'overbought1': float(current['wt1']) >= self.ob_level1,
            'overbought2': float(current['wt1']) >= self.ob_level2,
            'oversold1': float(current['wt1']) <= self.os_level1,
            'oversold2': float(current['wt1']) <= self.os_level2,
            'cross_over': previous is not None and float(current['wt1']) > float(current['wt2']) and float(previous['wt1']) <= float(previous['wt2']),
            'cross_under': previous is not None and float(current['wt1']) < float(current['wt2']) and float(previous['wt1']) >= float(previous['wt2'])
        }

# Create singleton instance
indicators = Indicators()