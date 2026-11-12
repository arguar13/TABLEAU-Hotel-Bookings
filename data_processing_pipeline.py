import os
import pandas as pd
import urllib.request
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def run_pipeline():
    """Download the hotel bookings data, clean it and add the revenue fields used in Tableau."""
    # __file__ does not exist when the code runs in a notebook or a REPL
    current_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
    raw_data_path = os.path.join(current_dir, 'hotel_bookings.csv')
    processed_data_path = os.path.join(current_dir, 'end_processed_hotel_bookings.csv')

    dataset_url = "https://raw.githubusercontent.com/rfordatascience/tidytuesday/master/data/2020/2020-02-11/hotels.csv"
    
    logging.info("Downloading raw dataset...")
    try:
        urllib.request.urlretrieve(dataset_url, raw_data_path)
        logging.info(f"Dataset downloaded successfully and saved to: {raw_data_path}")
    except Exception as e:
        logging.error(f"Failed to download dataset: {e}")
        return

    logging.info("Loading data for processing...")
    df = pd.read_csv(raw_data_path)

    logging.info("Processing data...")

    # agent/company are NULL when the booking had none; 0 keeps both columns numeric
    df['children'] = df['children'].fillna(0)
    df['country'] = df['country'].fillna('Unknown')
    df['agent'] = df['agent'].fillna(0)
    df['company'] = df['company'].fillna(0)

    df['total_stay_nights'] = df['stays_in_weekend_nights'] + df['stays_in_week_nights']

    # Remove anomalous data (e.g., zero nights stay or negative daily rate)
    df = df[(df['total_stay_nights'] > 0) & (df['adr'] >= 0)]

    # Identical rows are kept on purpose. The dataset has no booking ID, and 26.8% of
    # the rows repeat another one, mostly where several rooms are booked together
    # (75% of the 'Groups' rows are repeated; Groups, Offline TA/TO and Online TA hold
    # 46.5%, 32.3% and 15.2% of the copies). A repeated row is read as another room of
    # the same booking, so for revenue accounting the unit of analysis is the room booking.

    # Booked value of the stay: adr is the average daily rate (EUR)
    df['total_revenue'] = df['total_stay_nights'] * df['adr']

    month_map = {
        'January': 1, 'February': 2, 'March': 3, 'April': 4,
        'May': 5, 'June': 6, 'July': 7, 'August': 8,
        'September': 9, 'October': 10, 'November': 11, 'December': 12
    }
    df['arrival_month_num'] = df['arrival_date_month'].map(month_map)
    
    df['arrival_date'] = pd.to_datetime({
        'year': df['arrival_date_year'],
        'month': df['arrival_month_num'],
        'day': df['arrival_date_day_of_month']
    })

    df = df.drop(columns=['arrival_month_num'])

    def categorize_lead_time(days):
        if days <= 7: return 'Last Minute (0-7 days)'
        elif days <= 30: return 'Short Term (8-30 days)'
        elif days <= 90: return 'Medium Term (31-90 days)'
        else: return 'Long Term (90+ days)'
        
    df['lead_time_segment'] = df['lead_time'].apply(categorize_lead_time)

    # Calculate Lost Revenue due to cancellations
    # A cancelled booking under a non-refundable deposit is not fully lost: the hotel keeps
    # the deposit, so only cancellations without that protection count as lost revenue
    is_canceled = df['is_canceled'] == 1
    is_protected = df['deposit_type'] == 'Non Refund'
    df['lost_revenue'] = df['total_revenue'].where(is_canceled & ~is_protected, 0)
    df['realized_revenue'] = df['total_revenue'].where(~is_canceled, 0)

    logging.info("Saving processed dataset...")
    df.to_csv(processed_data_path, index=False)
    logging.info(f"Pipeline completed! Processed data ready for Tableau at: {processed_data_path}")

if __name__ == "__main__":
    run_pipeline()