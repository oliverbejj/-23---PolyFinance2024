import yfinance as yf
import pandas as pd

def get_opening_values(ticker: str) -> dict:
    """
    Fetches the historical opening values of a given stock ticker for the past year.

    Parameters:
        ticker (str): The stock ticker symbol (e.g., 'AAPL' for Apple Inc.)

    Returns:
        dict: A dictionary with dates as keys and opening values as values.
    """
    # Fetch historical data for the specified ticker
    stock = yf.Ticker(ticker)
    historical_data = stock.history(period="1y", interval="1d")  # 1 year of daily data

    # Extract date and opening values into a dictionary
    opening_values = {str(date): row['Open'] for date, row in historical_data.iterrows()}
    
    return opening_values