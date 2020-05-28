import pandas as pd
import matplotlib.pyplot as plt


# todo: consider transaction fee


class Record:
    def __init__(self, date, price_info):
        self.date = date
        self.price_info = price_info


class PriceInfo:
    def __init__(self, highest, lowest, last, avg):
        self.highest = highest
        self.lowest = lowest
        self.last = last
        self.avg = avg

class Mesh:
    def __init__(self, wallet, code):
        self.mesh_code = code
        self.wallet = wallet
        self.mesh_unit = [] # sorted from high to low
    def decide(self, date_idx, date, cur_price_info):
        cur_high = cur_price_info.highest
        cur_low = cur_price_info.lowest
#         print("[%s] today high: %.2f, low: %.2f" % (date, cur_high, cur_low))
        # if there is unit should be selled, then sell
        for unit in self.mesh_unit:
            if unit.sell_price > cur_high:
                # no chance to sell
                continue
            if unit.filled:
                # sell
                self.wallet.fund += unit.volume * unit.sell_price # 改进：观察开盘集合竞价，如果sell price处于最低价以下，可以以最低价卖出
                self.wallet.fund -= 5 # transaction fee
                revenue = unit.volume * (unit.sell_price - unit.buy_price)
                unit.volume = 0.0
                unit.filled = False
                print("sell: ", (date_idx, date, self.mesh_code, True, unit.buy_price, unit.sell_price, revenue))
                # date_idx, date, code, isSell, buy_price, sell_price, revenue
                self.wallet.transactions.append((date_idx, date, self.mesh_code, True, unit.buy_price, unit.sell_price, revenue))
        # find unit to buy
        for unit in self.mesh_unit:
            if unit.buy_price < cur_low or unit.buy_price > cur_high:
                # no chance to buy
                continue
            if unit.filled:
                # have bought
                continue
            # buy
            self.wallet.fund -= unit.each_transaction_volume * unit.buy_price
            self.wallet.fund -= 5 # transaction fee
            unit.volume = unit.each_transaction_volume
            unit.filled = True
            print("buy: ", (date_idx, date, self.mesh_code, False, unit.each_transaction_volume, unit.buy_price, 0, 0))
            # date_idx, date, code, isSell, vol, buy_price, sell_price, revenue
            self.wallet.transactions.append((date_idx, date, self.mesh_code, False, unit.buy_price, 0, 0))
    def generate_mesh(self, init_price, unit_size_percent, each_transaction_money, price_limits, unit_add_percent=0):
        # price_limits should be (lower_bound, upper_bound)
        cur_buy_price = init_price
        this_trans_money = each_transaction_money
        while cur_buy_price < price_limits[1]:
            cur_sell_price = cur_buy_price * (1+unit_size_percent/100)
            print("buy=", cur_buy_price)
            print("this_trans_money=", this_trans_money)
            this_trans_vol = this_trans_money / cur_buy_price
            print("vol=", this_trans_vol)
            new_unit = MeshUnit(cur_buy_price, cur_sell_price, 0.0, this_trans_vol, this_trans_money)
            self.mesh_unit.append(new_unit)
            this_trans_money = this_trans_money / (1+unit_add_percent/100)
            cur_buy_price = cur_sell_price
        cur_sell_price = init_price
        this_trans_money = each_transaction_money
        while cur_sell_price > price_limits[0]:
            cur_buy_price = cur_sell_price * (1-unit_size_percent/100)
            this_trans_money = this_trans_money * (1+unit_add_percent/100)
            print("buy=", cur_buy_price)

            print("this_trans_money=", this_trans_money)
            this_trans_vol = this_trans_money / cur_buy_price
            print("vol=", this_trans_vol)
            new_unit = MeshUnit(cur_buy_price, cur_sell_price, 0.0, this_trans_vol, this_trans_money)
            self.mesh_unit.append(new_unit)
            cur_sell_price = cur_buy_price
        self.mesh_unit = sorted(self.mesh_unit, key=(lambda x: x.buy_price), reverse=True)
        for u in self.mesh_unit:
            u.print()
    def mesh_to_csv(self, filename):
        fp = open(filename, "w")
        writer = csv.writer(fp)

        for u in self.mesh_unit:
            writer.writerow((u.buy_price, u.sell_price, u.each_trans_money))

    def get_asset(self, cur_price_info):
        # get current asset
        asset = 0.0
        for u in self.mesh_unit:
            if not u.filled:
                continue
            asset += cur_price_info.last * u.volume
        return asset
class MeshUnit:
    def __init__(self, buy_price, sell_price, volume, each_transaction_volume, each_trans_money):
        self.buy_price = buy_price
        self.sell_price = sell_price
        self.volume = volume
        self.each_transaction_volume = each_transaction_volume
        self.each_trans_money = each_trans_money
        self.filled = False
    def print(self):
        print("[Unit] b: %.3f, s: %.3f, vol: %.1f" % (self.buy_price, self.sell_price, self.each_transaction_volume))


class Wallet:
    def __init__(self, init_fund):
        self.init_fund = init_fund
        self.fund = init_fund
        self.mesh = []  # store the state of each mesh
        self.transactions = [] # store the transaction record
        self.state = []
    def add_mesh(self, mesh):
        self.mesh.append(mesh)
    def decide(self, date_idx, date, price_info_map):
        # 网格决策
        for m in self.mesh:
            m.decide(date_idx, date, price_info_map[m.mesh_code])
        self.store_state(date, price_info_map)
    def store_state(self, date, price_info_map):
        # store today's state & compute revenue and asset
        asset = 0.0
        price_list = [0] * len(self.mesh)
        for i, m in enumerate(self.mesh):
            asset += m.get_asset(price_info_map[m.mesh_code])
            price_list[i] = price_info_map[m.mesh_code].last
        revenue = asset + self.fund - self.init_fund
        total_asset = asset + self.fund
        # (date, fund, asset, revenue, total_asset, price_list)
        self.state.append((date, self.fund, asset, revenue, total_asset, price_list))
#         print("[%s] fund=%.2f, asset=%.2f, revenue=%.2f" % (date, self.fund, asset, revenue))
    def output_result(self, figname="result.png"):
        # print the final results
        time_index, fund_series, asset_series, revenue_series, total_asset_series, price_series = [], [], [], [], [], []
        rvn_ratios = []
        lowest_fund = self.init_fund
        for s in self.state:
            time_index.append(s[0])
            if s[1] < lowest_fund:
                lowest_fund = s[1]
            fund_series.append(s[1])
            asset_series.append(s[2])
            revenue_series.append(s[3])
            total_asset_series.append(s[4])
            price_series.append(s[5][0])
            total_used_fund = (self.init_fund - lowest_fund)
            rvn_ratio = 0
            if total_used_fund > 0:
                rvn_ratio = s[3]/total_used_fund * 100
            rvn_ratios.append(rvn_ratio)
        df = pd.DataFrame({"date": pd.to_datetime(time_index), "fund": fund_series, "asset": asset_series,
                           "total_asset": total_asset_series,
                           "revenue": revenue_series, "price": price_series, "rvn_ratio": rvn_ratios})
        df = df.set_index("date")
        print(df.tail(4))

        plt.figure(figsize=(15, 12))
        ax = plt.subplot(6,1,1)
        df["price"].plot(title="Price")
        plt.grid()
        plt.subplot(6,1,2,sharex=ax)
        df["asset"].plot(title="Asset")
        plt.grid()
        plt.subplot(6,1,3,sharex=ax)
        df["total_asset"].plot(title="Total Asset")
        plt.grid()
        plt.subplot(6,1,4,sharex=ax)
        df["fund"].plot(title="Money")
        plt.grid()
        plt.subplot(6,1,5,sharex=ax)
        df["revenue"].plot(title="Revenue")
        plt.grid()
        plt.subplot(6,1,6,sharex=ax)
        df["rvn_ratio"].plot(title="Revenue Ratio (%)")
        plt.grid()


        plt.savefig(figname)

if __name__ == "__main__":
    stock = '512660.SH'
    config = {
        "init": 0.78,
        "price_gap_pct": 5,
        "unit": 5000,
        "limits": (0.6, 1.3),
        "unit_add_pct": 10,
    }

    stock = '515050.SH'
    config = {
        "init": 1.067,
        "price_gap_pct": 5,
        "unit": 5000,
        "limits": (0.7, 1.2),
        "unit_add_pct": 10,
    }
    '''
    stock = '512000.SH'
    config = {
        "init": 0.87,
        "price_gap_pct": 5,
        "unit": 5000,
        "limits": (0.5, 1.1),
        "unit_add_pct": 10,
    }
    '''
    history_filename = stock + ".csv"
    db = []
    name = "%s_%d%%_(%f-%f)_%d%%" % (stock, config["price_gap_pct"], config["limits"][0], config["limits"][1], config["unit_add_pct"])
    import csv
    with open(history_filename) as f:
        cnt = 0
        reader = csv.reader(f)
        for row in reader:
            cnt += 1
            if cnt == 1:
                continue
    #         print(row)
            if cnt < 2:
                continue
            if len(row) < 12:
                continue
            # highest, lowest, last, avg
            db.append(Record(row[2], PriceInfo(float(row[5]), float(row[6]), float(row[7]), float(row[12]))))
    wallet = Wallet(50000)
    mesh = Mesh(wallet, stock)
    mesh.generate_mesh(config["init"], config["price_gap_pct"], config["unit"],config["limits"], unit_add_percent=config["unit_add_pct"])
    mesh.mesh_to_csv("strategy/%s.csv" % (name))
    wallet.add_mesh(mesh)
    for idx, r in enumerate(db):
        wallet.decide(idx, r.date, {stock: r.price_info})
    wallet.output_result(figname="output/%s.png" % (name))
