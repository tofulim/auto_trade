def get_rsi(target_df, n_days: int):
    close_diff = target_df.tail(n_days)['Close'].diff()
    avg_gains = close_diff[close_diff > 0].mean()
    avg_loss = -close_diff[close_diff < 0].mean()

    # 상대강도
    rs = avg_gains / avg_loss
    # RSI
    rsi = 100 - (100 / (1 + rs))

    return float(round(rsi, 2))

def get_moving_averages(target_df):
    day5_close_avg, day10_close_avg, day20_close_avg, day60_close_avg = target_df["Close"][-5:].mean(), target_df["Close"][-10:].mean(), target_df["Close"][-20:].mean(), target_df["Close"][-60:].mean()

    return float(round(day5_close_avg)), float(round(day10_close_avg)), float(round(day20_close_avg)), float(round(day60_close_avg))

def get_zscore(target_df, n_days: int):
    target_close_series = target_df.tail(n_days)["Close"]
    today_close, close_mean, close_std = target_close_series.iloc[-1], target_close_series.mean(), target_close_series.std()

    zscore = (today_close - close_mean) / close_std
    return float(round(zscore))
