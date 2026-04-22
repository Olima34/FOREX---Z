COUNTRIES = {
    "australia": {
        "gdp-growth": "GDP Growth Rate QoQ", "interest-rate": "RBA Interest Rate Decision",
        "unemployment-rate": "Unemployment Rate", "inflation-cpi": "Inflation Rate YoY",
        "balance-of-trade": "Balance of Trade", "current-account": "Current Account",
        "retail-sales": "Retail Sales MoM"
    },
    "canada": {
        "gdp-growth": "QoQ", "interest-rate": "BoC Interest Rate Decision",
        "unemployment-rate": "Unemployment Rate", "inflation-cpi": "Inflation Rate YoY",
        "balance-of-trade": "Balance of Trade", "current-account": "Current Account",
        "retail-sales": "Retail Sales MoM Final"
    },
    "euro-area": {
        "gdp-growth": "QoQ 3rd Est", "interest-rate": "ECB Interest Rate Decision",
        "unemployment-rate": "Unemployment Rate", "inflation-cpi": "Inflation Rate YoY Final",
        "balance-of-trade": "Balance of Trade", "current-account": "Current Account",
        "retail-sales": "Retail Sales MoM"
    },
    "japan": {
        "gdp-growth": "QoQ Final", "interest-rate": "BoJ Interest Rate Decision",
        "unemployment-rate": "Unemployment Rate", "inflation-cpi": "Inflation Rate YoY",
        "balance-of-trade": "Balance of Trade", "current-account": "Current Account",
        "retail-sales": "Retail Sales MoM"
    },
    "new-zealand": {
        "gdp-growth": "GDP Growth Rate QoQ", "interest-rate": "RBNZ Interest Rate Decision",
        "unemployment-rate": "Unemployment Rate", "inflation-cpi": "Inflation Rate YoY",
        "balance-of-trade": "Balance of Trade", "current-account": "Current Account",
        "retail-sales": "Retail Sales QoQ"
    },
    "switzerland": {
        "gdp-growth": "QoQ Final", "interest-rate": "SNB Interest Rate Decision",
        "unemployment-rate": "Unemployment Rate", "inflation-cpi": "Inflation Rate YoY",
        "balance-of-trade": "Balance of Trade", "current-account": "Current Account",
        "retail-sales": "Retail Sales MoM"
    },
    "united-states": {
        "gdp-growth": "QoQ Final", "interest-rate": "Fed Interest Rate Decision",
        "unemployment-rate": "Unemployment Rate", "inflation-cpi": "Inflation Rate YoY",
        "balance-of-trade": "Balance of Trade", "current-account": "Current Account",
        "retail-sales": "Retail Sales MoM"
    },
    "united-kingdom": {
        "gdp-growth": "QoQ Final", "interest-rate": "BoE Interest Rate Decision",
        "unemployment-rate": "Unemployment Rate", "inflation-cpi": "Inflation Rate YoY",
        "balance-of-trade": "Balance of Trade", "current-account": "Current Account",
        "retail-sales": "Retail Sales MoM"
    }
}

COT_COLUMNS = [
    "Market_and_Exchange_Names", "As_of_Date_In_Form_YYMMDD", "As_of_Date_In_Form_YYYY-MM-DD",
    "CFTC_Contract_Market_Code", "CFTC_Market_Code_in_Initials", "CFTC_Region_Code",
    "CFTC_Commodity_Code", "Open_Interest_All", "Noncommercial_Positions_Long_All",
    "Noncommercial_Positions_Short_All", "Noncommercial_Positions_Spreading_All",
    "Commercial_Positions_Long_All", "Commercial_Positions_Short_All", "Total_Reportable_Positions_Long_All",
    "Total_Reportable_Positions_Short_All", "NonReportable_Positions_Long_All",
    "NonReportable_Positions_Short_All", "Open_Interest_Old", "Noncommercial_Positions_Long_Old",
    "Noncommercial_Positions_Short_Old", "Noncommercial_Positions_Spreading_Old",
    "Commercial_Positions_Long_Old", "Commercial_Positions_Short_Old", "Total_Reportable_Positions_Long_Old",
    "Total_Reportable_Positions_Short_Old", "NonReportable_Positions_Long_Old",
    "NonReportable_Positions_Short_Old", "Open_Interest_Other", "Noncommercial_Positions_Long_Other",
    "Noncommercial_Positions_Short_Other", "Noncommercial_Positions_Spreading_Other",
    "Commercial_Positions_Long_Other", "Commercial_Positions_Short_Other",
    "Total_Reportable_Positions_Long_Other", "Total_Reportable_Positions_Short_Other",
    "NonReportable_Positions_Long_Other", "NonReportable_Positions_Short_Other",
    "Change_in_Open_Interest_All", "Change_in_Noncommercial_Long_All",
    "Change_in_Noncommercial_Short_All", "Change_in_Noncommercial_Spreading_All",
    "Change_in_Commercial_Long_All", "Change_in_Commercial_Short_All",
    "Change_in_Total_Reportable_Long_All", "Change_in_Total_Reportable_Short_All",
    "Change_in_NonReportable_Long_All", "Change_in_NonReportable_Short_All",
    "Pct_of_Open_Interest_All", "Pct_of_OI_Noncommercial_Long_All",
    "Pct_of_OI_Noncommercial_Short_All", "Pct_of_OI_Noncommercial_Spreading_All",
    "Pct_of_OI_Commercial_Long_All", "Pct_of_OI_Commercial_Short_All",
    "Pct_of_OI_Total_Reportable_Long_All", "Pct_of_OI_Total_Reportable_Short_All",
    "Pct_of_OI_NonReportable_Long_All", "Pct_of_OI_NonReportable_Short_All",
    "Pct_of_Open_Interest_Old", "Pct_of_OI_Noncommercial_Long_Old",
    "Pct_of_OI_Noncommercial_Short_Old", "Pct_of_OI_Noncommercial_Spreading_Old",
    "Pct_of_OI_Commercial_Long_Old", "Pct_of_OI_Commercial_Short_Old",
    "Pct_of_OI_Total_Reportable_Long_Old", "Pct_of_OI_Total_Reportable_Short_Old",
    "Pct_of_OI_NonReportable_Long_Old", "Pct_of_OI_NonReportable_Short_Old",
    "Pct_of_Open_Interest_Other", "Pct_of_OI_Noncommercial_Long_Other",
    "Pct_of_OI_Noncommercial_Short_Other", "Pct_of_OI_Noncommercial_Spreading_Other",
    "Pct_of_OI_Commercial_Long_Other", "Pct_of_OI_Commercial_Short_Other",
    "Pct_of_OI_Total_Reportable_Long_Other", "Pct_of_OI_Total_Reportable_Short_Other",
    "Pct_of_OI_NonReportable_Long_Other", "Pct_of_OI_NonReportable_Short_Other",
    "Traders_Total_All", "Traders_Noncommercial_Long_All", "Traders_Noncommercial_Short_All",
    "Traders_Noncommercial_Spreading_All", "Traders_Commercial_Long_All",
    "Traders_Commercial_Short_All", "Traders_Total_Reportable_Long_All",
    "Traders_Total_Reportable_Short_All", "Traders_Total_Old",
    "Traders_Noncommercial_Long_Old", "Traders_Noncommercial_Short_Old",
    "Traders_Noncommercial_Spreading_Old", "Traders_Commercial_Long_Old",
    "Traders_Commercial_Short_Old", "Traders_Total_Reportable_Long_Old",
    "Traders_Total_Reportable_Short_Old", "Traders_Total_Other",
    "Traders_Noncommercial_Long_Other", "Traders_Noncommercial_Short_Other",
    "Traders_Noncommercial_Spreading_Other", "Traders_Commercial_Long_Other",
    "Traders_Commercial_Short_Other", "Traders_Total_Reportable_Long_Other",
    "Traders_Total_Reportable_Short_Other", "Conc_Gross_LE_4_TDR_Long_All",
    "Conc_Gross_LE_4_TDR_Short_All", "Conc_Gross_LE_8_TDR_Long_All",
    "Conc_Gross_LE_8_TDR_Short_All", "Conc_Net_LE_4_TDR_Long_All",
    "Conc_Net_LE_4_TDR_Short_All", "Conc_Net_LE_8_TDR_Long_All",
    "Conc_Net_LE_8_TDR_Short_All", "Conc_Gross_LE_4_TDR_Long_Old",
    "Conc_Gross_LE_4_TDR_Short_Old", "Conc_Gross_LE_8_TDR_Long_Old",
    "Conc_Gross_LE_8_TDR_Short_Old", "Conc_Net_LE_4_TDR_Long_Old",
    "Conc_Net_LE_4_TDR_Short_Old", "Conc_Net_LE_8_TDR_Long_Old",
    "Conc_Net_LE_8_TDR_Short_Old", "Conc_Gross_LE_4_TDR_Long_Other",
    "Conc_Gross_LE_4_TDR_Short_Other", "Conc_Gross_LE_8_TDR_Long_Other",
    "Conc_Gross_LE_8_TDR_Short_Other", "Conc_Net_LE_4_TDR_Long_Other",
    "Conc_Net_LE_4_TDR_Short_Other", "Conc_Net_LE_8_TDR_Long_Other",
    "Conc_Net_LE_8_TDR_Short_Other", "Contract_Units",
    "CFTC_Contract_Market_Code_Quotes", "CFTC_Market_Code_in_Initials_Quotes",
    "CFTC_Commodity_Code_Quotes"
]

COT_PAIRS = {
    "AUDUSD": ("AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE", "USD INDEX - ICE FUTURES U.S."),
    "AUDGBP": ("AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE", "BRITISH POUND - CHICAGO MERCANTILE EXCHANGE"),
    "AUDJPY": ("AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE", "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE"),
    "AUDCAD": ("AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE", "CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE"),
    "AUDCHF": ("AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE", "SWISS FRANC - CHICAGO MERCANTILE EXCHANGE"),
    "AUDNZD": ("AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE", "NZ DOLLAR - CHICAGO MERCANTILE EXCHANGE"),
    "CADJPY": ("CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE", "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE"),
    "CADCHF": ("CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE", "SWISS FRANC - CHICAGO MERCANTILE EXCHANGE"),
    "CHFJPY": ("SWISS FRANC - CHICAGO MERCANTILE EXCHANGE", "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE"),
    "EURUSD": ("EURO FX - CHICAGO MERCANTILE EXCHANGE", "USD INDEX - ICE FUTURES U.S."),
    "EURJPY": ("EURO FX - CHICAGO MERCANTILE EXCHANGE", "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE"),
    "EURCAD": ("EURO FX - CHICAGO MERCANTILE EXCHANGE", "CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE"),
    "EURCHF": ("EURO FX - CHICAGO MERCANTILE EXCHANGE", "SWISS FRANC - CHICAGO MERCANTILE EXCHANGE"),
    "EURAUD": ("EURO FX - CHICAGO MERCANTILE EXCHANGE", "AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE"),
    "EURNZD": ("EURO FX - CHICAGO MERCANTILE EXCHANGE", "NZ DOLLAR - CHICAGO MERCANTILE EXCHANGE"),
    "GBPUSD": ("BRITISH POUND - CHICAGO MERCANTILE EXCHANGE", "USD INDEX - ICE FUTURES U.S."),
    "GBPJPY": ("BRITISH POUND - CHICAGO MERCANTILE EXCHANGE", "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE"),
    "GBPCAD": ("BRITISH POUND - CHICAGO MERCANTILE EXCHANGE", "CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE"),
    "GBPCHF": ("BRITISH POUND - CHICAGO MERCANTILE EXCHANGE", "SWISS FRANC - CHICAGO MERCANTILE EXCHANGE"),
    "NZDUSD": ("NZ DOLLAR - CHICAGO MERCANTILE EXCHANGE", "USD INDEX - ICE FUTURES U.S."),
    "NZDJPY": ("NZ DOLLAR - CHICAGO MERCANTILE EXCHANGE", "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE"),
    "NZDCAD": ("NZ DOLLAR - CHICAGO MERCANTILE EXCHANGE", "CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE"),
    "NZDCHF": ("NZ DOLLAR - CHICAGO MERCANTILE EXCHANGE", "SWISS FRANC - CHICAGO MERCANTILE EXCHANGE"),
    "USDJPY": ("USD INDEX - ICE FUTURES U.S.", "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE"),
    "USDCAD": ("USD INDEX - ICE FUTURES U.S.", "CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE"),
    "USDCHF": ("USD INDEX - ICE FUTURES U.S.", "SWISS FRANC - CHICAGO MERCANTILE EXCHANGE"),
}

PAIRS = {
    "AUDUSD": ("australia", "united-states"),
    "AUDGBP": ("australia", "united-kingdom"),
    "AUDJPY": ("australia", "japan"),
    "AUDCAD": ("australia", "canada"),
    "AUDCHF": ("australia", "switzerland"),
    "AUDNZD": ("australia", "new-zealand"),
    "CADJPY": ("canada", "japan"),
    "CADCHF": ("canada", "switzerland"),
    "CHFJPY": ("switzerland", "japan"),
    "EURUSD": ("euro-area", "united-states"),
    "EURJPY": ("euro-area", "japan"),
    "EURCAD": ("euro-area", "canada"),
    "EURCHF": ("euro-area", "switzerland"),
    "EURAUD": ("euro-area", "australia"),
    "EURNZD": ("euro-area", "new-zealand"),
    "GBPUSD": ("united-kingdom", "united-states"),
    "GBPJPY": ("united-kingdom", "japan"),
    "GBPCAD": ("united-kingdom", "canada"),
    "GBPCHF": ("united-kingdom", "switzerland"),
    "NZDUSD": ("new-zealand", "united-states"),
    "NZDJPY": ("new-zealand", "japan"),
    "NZDCAD": ("new-zealand", "canada"),
    "NZDCHF": ("new-zealand", "switzerland"),
    "USDJPY": ("united-states", "japan"),
    "USDCAD": ("united-states", "canada"),
    "USDCHF": ("united-states", "switzerland"),
}

# Les coefficients sont centralisés dans utils/parametres.py.
# On les ré-exporte ici pour que les anciens imports continuent de fonctionner.
from utils.parametres import INDICATOR_COEFFICIENTS  # noqa: E402,F401

COT_NAMES = [
    "EURO FX - CHICAGO MERCANTILE EXCHANGE", "USD INDEX - ICE FUTURES U.S.",
    "BRITISH POUND - CHICAGO MERCANTILE EXCHANGE", "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE",
    "CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE", "SWISS FRANC - CHICAGO MERCANTILE EXCHANGE",
    "AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE", "NZ DOLLAR - CHICAGO MERCANTILE EXCHANGE",
]

INDICATORS = ["gdp-growth", "interest-rate", "unemployment-rate", "inflation-cpi",
              "balance-of-trade", "current-account", "retail-sales"]

BAD_INDICATORS = ['unemployment-rate']

SYMBOLS = {'A$': '', 'C$': '', 'NZ$': '', '$': '', '€': '', '£': '', '¥': '', 'CHF': ''}

UNITS = {'%': 1, 'B': 1e9, 'M': 1e6, 'K': 1e3}
