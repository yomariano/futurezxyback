import numpy as np
import pandas as pd
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from typing import List, Dict, Any
from datetime import datetime
import ta
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Indicators:
    def __init__(self):
        self.n1 = 10  # Channel Length
        self.n2 = 21  # Average Length
        self.ob_level1 = 60   # Overbought Level 1
        self.ob_level2 = 53   # Overbought Level 2
        self.os_level1 = -60  # Oversold Level 1
        self.os_level2 = -53  # Oversold Level 2
        self.sma50_period = 50
        self.sma200_period = 200

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
            
            print(f"Time: {timestamp} "
                  f"H: {df.iloc[i]['high']:.6f} "
                  f"L: {df.iloc[i]['low']:.6f} "
                  f"C: {df.iloc[i]['close']:.6f} "
                  f"AP: {df.iloc[i]['ap']:.6f} "
                  f"EMA: {df.iloc[i]['esa']:.6f} "
                  f"D: {df.iloc[i]['d']:.6f} "
                  f"WT1: {df.iloc[i]['wt1']:.6f} "
                  f"WT2: {wt2_str} "
                  f"OB1: {float(df.iloc[i]['wt1']) >= self.ob_level1} "
                  f"OB2: {float(df.iloc[i]['wt1']) >= self.ob_level2} "
                  f"OS1: {float(df.iloc[i]['wt1']) <= self.os_level1} "
                  f"OS2: {float(df.iloc[i]['wt1']) <= self.os_level2} "
                  f"CrossOver: {i > 0 and float(df.iloc[i]['wt1']) > float(df.iloc[i]['wt2']) and float(df.iloc[i-1]['wt1']) <= float(df.iloc[i-1]['wt2'])} "
                  f"CrossUnder: {i > 0 and float(df.iloc[i]['wt1']) < float(df.iloc[i]['wt2']) and float(df.iloc[i-1]['wt1']) >= float(df.iloc[i-1]['wt2'])}")

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

    def calculate_moving_averages(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(candles) < self.sma200_period:
            raise ValueError(f"Not enough candles to calculate SMAs. Need at least {self.sma200_period} candles, but got {len(candles)}")

        # Sort candles by timestamp in descending order (newest first)
        sorted_candles = sorted(candles, key=lambda x: x['timestamp'], reverse=True)
        
        # Convert sorted candles to pandas DataFrame
        df = pd.DataFrame(sorted_candles)
        
        # Calculate SMAs on the reversed data (oldest to newest)
        df['sma50'] = df['close'].iloc[::-1].rolling(window=self.sma50_period, min_periods=self.sma50_period).mean().iloc[::-1]
        df['sma200'] = df['close'].iloc[::-1].rolling(window=self.sma200_period, min_periods=self.sma200_period).mean().iloc[::-1]
        
        # Get current values (first row since data is already newest first)
        current = df.iloc[0]
        
        return {
            'sma50': float(current['sma50']) if not pd.isna(current['sma50']) else 0.0,
            'sma200': float(current['sma200']) if not pd.isna(current['sma200']) else 0.0,
            'price_above_sma50': float(current['close']) > float(current['sma50']) if not pd.isna(current['sma50']) else False,
            'price_above_sma200': float(current['close']) > float(current['sma200']) if not pd.isna(current['sma200']) else False,
            'sma50_above_sma200': float(current['sma50']) > float(current['sma200']) if not pd.isna(current['sma50']) and not pd.isna(current['sma200']) else False
        }

    def calculate_rsi(self, candles, period=14):
        """Calculate RSI using ta library's RSIIndicator."""
        try:
            # Sort candles by timestamp in ascending order (oldest first)
            sorted_candles = sorted(candles, key=lambda x: x['timestamp'])
            
            # Convert to pandas DataFrame and extract close prices
            df = pd.DataFrame(sorted_candles)
            price_series = pd.Series([float(p) for p in df['close']])
            
            # Calculate RSI using ta library
            rsi_indicator = RSIIndicator(
                close=price_series,
                window=period,
                fillna=True
            )
            rsi = rsi_indicator.rsi()
            
            # Debug logging
            logger.info('\nLast 10 positions of RSI calculation:')
            for i in range(min(10, len(price_series))):
                logger.info(
                    f"Position -{i}: "
                    f"Price: {price_series.iloc[-(i+1)]:.2f}, "
                    f"RSI: {rsi.iloc[-(i+1)]:.2f}"
                )
            
            logger.info(f"Number of prices: {len(price_series)}, Number of RSI values: {len(rsi)}")
            
            return rsi
            
        except Exception as e:
            logger.error(f"Error calculating RSI: {str(e)}")
            return pd.Series()  # Return empty series on error

    def calculate_rsi_divergences(self, candles: List[Dict[str, Any]], lookback_left: int = 5, lookback_right: int = 5) -> Dict[str, bool]:
        try:
            signals = {
                'bullish_divergence': False,
                'hidden_bullish_divergence': False,
                'bearish_divergence': False,
                'hidden_bearish_divergence': False
            }

            if len(candles) < 20:  # Minimum candles needed for reliable RSI and divergence calculation
                logger.info("Not enough candles for RSI divergence calculation")
                return signals

            # Convert candles to DataFrame
            df = pd.DataFrame(sorted(candles, key=lambda x: x['timestamp'], reverse=True))
            df = df.reset_index(drop=True)  # Reset index to avoid comparison issues
            
            # Calculate RSI
            rsi_series = self.calculate_rsi(candles)
            rsi_series = rsi_series.reset_index(drop=True)  # Reset index to avoid comparison issues

            # Debug logging
            logger.info(f"RSI Divergence calculation - Number of candles: {len(candles)}")
            logger.info(f"RSI Series length: {len(rsi_series)}")

            # Pivot points
            pl_found = rsi_series.rolling(window=lookback_left + lookback_right + 1).min().shift(-lookback_right).notna()
            ph_found = rsi_series.rolling(window=lookback_left + lookback_right + 1).max().shift(-lookback_right).notna()

            if len(pl_found) > 0 and len(ph_found) > 0:
                # Regular Bullish Divergence
                rsi_hl = (rsi_series.shift(lookback_right) > rsi_series.shift(lookback_right + 1)) & pl_found
                price_ll = (df['low'].shift(lookback_right) < df['low'].shift(lookback_right + 1))
                bull_cond = price_ll & rsi_hl & pl_found

                signals['bullish_divergence'] = bull_cond.any()

                # Hidden Bullish Divergence
                rsi_ll = (rsi_series.shift(lookback_right) < rsi_series.shift(lookback_right + 1)) & pl_found
                price_hl = (df['low'].shift(lookback_right) > df['low'].shift(lookback_right + 1))
                hidden_bull_cond = price_hl & rsi_ll & pl_found

                signals['hidden_bullish_divergence'] = hidden_bull_cond.any()

                # Regular Bearish Divergence
                rsi_lh = (rsi_series.shift(lookback_right) < rsi_series.shift(lookback_right + 1)) & ph_found
                price_hh = (df['high'].shift(lookback_right) > df['high'].shift(lookback_right + 1))
                bear_cond = price_hh & rsi_lh & ph_found

                signals['bearish_divergence'] = bear_cond.any()

                # Hidden Bearish Divergence
                rsi_hh = (rsi_series.shift(lookback_right) > rsi_series.shift(lookback_right + 1)) & ph_found
                price_lh = (df['high'].shift(lookback_right) < df['high'].shift(lookback_right + 1))
                hidden_bear_cond = price_lh & rsi_hh & ph_found

                signals['hidden_bearish_divergence'] = hidden_bear_cond.any()

            return signals

        except Exception as e:
            logger.error(f"Error calculating RSI Divergences: {str(e)}")
            return {
                'bullish_divergence': False,
                'hidden_bullish_divergence': False,
                'bearish_divergence': False,
                'hidden_bearish_divergence': False
            }

# Create singleton instance
indicators = Indicators()