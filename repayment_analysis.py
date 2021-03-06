from common_functions import log_to_csv, get_profit_table
import time, random
import datetime
import akshare as ak
import pandas as pd
import control_variables as cv
import workbook_manage as wm

def get_ipo_info():
    stock_ipo_info_df = ak.stock_ipo_info(cv.stock_code)
    log_to_csv(stock_ipo_info_df, 'IPO信息')
    global ipo_day
    ipo_day = stock_ipo_info_df[stock_ipo_info_df['item']=='上市日期']['value'].values[0]
    ipo_price = stock_ipo_info_df[stock_ipo_info_df['item'].str.contains('发行价')]['value'].values[0]
    return ipo_day, float(ipo_price)

def get_all_history_divided_detail():
    stock_history_dividend_detail_df = ak.stock_history_dividend_detail(indicator='分红', stock=cv.stock_code, date='')
    log_to_csv(stock_history_dividend_detail_df, '历史分红配股')
    return stock_history_dividend_detail_df

def get_implementation_divided_detail(df):
    return df.drop(df[(df['进度']=='预案')|(df['进度']=='不分配')].index)

def get_divided_next_market_day(df, ipo_price, data_dic):
    #第一行是ipo信息
    date_list = [df['除权除息日'].values[0]]
    price_list = [ipo_price]
    #获取交易日数据
    for day in df['除权除息日'].iloc[1:]:
        day_date = datetime.datetime.strptime(str(day), '%Y-%m-%d')
        stock_zh_a_hist_df = pd.DataFrame()
        while stock_zh_a_hist_df.empty:
            day_date += datetime.timedelta(1)
            query_date = day_date.strftime('%Y%m%d')
            stock_zh_a_hist_df = ak.stock_zh_a_hist(symbol=cv.stock_code, start_date=query_date, end_date=query_date)
        date_list.append(day_date.strftime('%Y-%m-%d'))
        price_list.append(stock_zh_a_hist_df['收盘'][0])
    data_dic['后一交易日日期'] = date_list
    data_dic['后一交易日股价'] = price_list
    return data_dic

def get_value_in_end_of_year(data_df):
    quantity_list = [cv.orig_quantity]
    last_year_quantity = cv.orig_quantity
    data_df = data_df.iloc[1:]
    for index, rows in data_df.iterrows():
        give_stock = int(last_year_quantity/10)*(rows['送股']+rows['转增'])
        bonus_stock = int(int(last_year_quantity/10)*rows['税前派息']/rows['后一交易日股价'])
        last_year_quantity += give_stock + bonus_stock
        quantity_list.append(last_year_quantity)
    return quantity_list

def get_sheet_name():
    return '股东回报'

def stock_value_info():
    # 获取发行信息
    ipo_day, ipo_price = get_ipo_info()
    # 获取原始分红信息
    stock_history_divided_detail_df = get_all_history_divided_detail()
    # 对 stock_history_dividend_detail_df 进行处理，删除未实施（预案/不分配）的行数据
    implementation_divided_detail_df = get_implementation_divided_detail(stock_history_divided_detail_df)
    # 原始df中插入ipo数据，有用的只有“除权除息日”
    implementation_divided_detail_df.loc['ipo'] = [ipo_day, '', '', '', '', ipo_day, '', '', '']
    # 按日期排序
    implementation_divided_detail_df = implementation_divided_detail_df.sort_values(by='除权除息日')
    # 生成新的数据：实施年份，除权除息日，送股，转增，税前派息，后一交易日日期，后一交易日股价，年底持股
    valid_data_dic = {
        '实施年份': [item[:4] for item in implementation_divided_detail_df['除权除息日']],
        '除权除息日': implementation_divided_detail_df['除权除息日'],
        '送股': implementation_divided_detail_df['送股(股)'],
        '转增': implementation_divided_detail_df['转增(股)'],
        '税前派息': implementation_divided_detail_df['派息(税前)(元)']
    }
    # 后一交易日日期，后一交易日股价
    valid_data_dic = get_divided_next_market_day(implementation_divided_detail_df, ipo_price, valid_data_dic)
    # 根据前面的信息计算出每年底持股
    valid_data_df = pd.DataFrame(valid_data_dic)
    valid_data_df['年底持股'] = get_value_in_end_of_year(valid_data_df)
    print(valid_data_df.to_string())
    # 生成excel对象
    wb_manage = wm.Workbook_Manage(get_sheet_name())
    # 表格写入excel
    wb_manage.write_dataframe(valid_data_df)
    return valid_data_df


def stock_value_calc(df):
    wb_manage = wm.Workbook_Manage(get_sheet_name())
    # 计算第二年持股市值，写入excel
    wb_manage.write_string(start_market_value_str(df))
    # 计算最后一次分红后持股市值，写入excel
    wb_manage.write_string(now_stock_value_str(df))
    # 计算收益率，写入excel
    wb_manage.write_string(rate_of_return_str(df))


def orig_stock_value_calc(df):
    return df.iloc[1]['后一交易日股价'] * df.iloc[1]['年底持股']

def start_market_value_str(df):
    return f'{df.iloc[1]["后一交易日日期"]} 持股市值 = {orig_stock_value_calc(df)}'

def now_stock_value_calc(df):
    return df.iloc[-1]['后一交易日股价'] * df.iloc[-1]['年底持股']

def now_stock_value_str(df):
    return f'{df.iloc[-1]["后一交易日日期"]} 持股市值 = {now_stock_value_calc(df)}'

def rate_of_return_str(df):
    total_years = int(df.iloc[-1]["实施年份"]) - int(df.iloc[1]["实施年份"])
    total_times = now_stock_value_calc(df) // orig_stock_value_calc(df)
    return f'{total_years} 年收益 {total_times} 倍，折合年化 {"%.2f" % annualized_rate_of_return_calc(total_years, total_times)}%'

def profit_value_calc():
    # 获取年报利润表
    stock_profit_table_df = get_profit_table()
    # 获取上市第一年，及上市第一年归母净利润
    first_year, first_profit = get_first_year_profit(stock_profit_table_df)
    # 获取最后一年，及最后一年归母净利润
    last_year, last_profit = get_last_year_profit(stock_profit_table_df)
    total_years = last_year - first_year
    total_times = last_profit // first_profit
    wb_manage = wm.Workbook_Manage(get_sheet_name())
    wb_manage.write_string(f'{first_year} 年净利润为 {first_profit}，{last_year} 年净利润为 {last_profit}，{total_years} 年增长 {total_times} 倍，折合年化 {"%.2f" % annualized_rate_of_return_calc(total_years, total_times)}%')

def get_first_year_profit(df):
    return int(ipo_day[0:4]), df["归属于母公司所有者的净利润"][df["报表日期"]==int(ipo_day[0:4])].values[0]

def get_last_year_profit(df):
    return df.iloc[-1]['报表日期'], df.iloc[-1]['归属于母公司所有者的净利润']

def annualized_rate_of_return_calc(years, times):
    return (pow(times, 1 / years) - 1) * 100

def repayment_analysis_data():
    stock_value_calc(stock_value_info())
    profit_value_calc()

if __name__ == '__main__':
    repayment_analysis_data()