//+------------------------------------------------------------------+
//| AlphaBasketAssistant.mq5                                          |
//| Semi-automatic trade assistant for the USDJPY basket              |
//| (Tokyo-open box breakout, gotobi fix short, month-end USD bid)    |
//|                                                                   |
//| What it does on its own: computes the setups at their clock      |
//| times, sizes the lot from the risk percent, shows a dashboard,   |
//| cancels the sibling stop order when one side fills, moves the    |
//| stop to break-even at +3R, closes the timed legs at their exit   |
//| time, deletes expired orders and blocks entries when the daily   |
//| or maximum loss guard is reached.                                 |
//| What it never does: open a trade. Every entry needs a click on   |
//| a PLACE button. This keeps it a trade-assistance / risk tool.    |
//|                                                                   |
//| Rules (from reference/gj-strat/green/BASKET.md, times UTC):      |
//|  Box: high/low of 23:30-00:29 (05:00-05:59 IST). 00:30: buy stop |
//|   at the high, sell stop at the low, one fills -> cancel other.  |
//|   SL = box + spread, TP = 9 x SL, at +3R move SL to entry + box/6|
//|   Stopped before 05:30 -> 6 minutes later one stop on the other  |
//|   side at the original box level (skip if price is past it).    |
//|   Orders expire 05:30. Max 2 trades a day, done after a TP.      |
//|   Only when ATR20 >= the 250-day median of ATR20.                 |
//|  Gotobi: 5/10/15/20/25/month-end (weekend -> Friday). 00:55 SELL |
//|   at market, SL 0.25 x ATR20, no TP, close 06:00. Vol filter on. |
//|  M-3: 3rd-last weekday of the month. 11:00 BUY at market,        |
//|   SL 0.25 x ATR20, no TP, close 12:00. Every month.               |
//+------------------------------------------------------------------+
#property copyright "Traders sir research programme, 2026"
#property version   "1.04"
#property description "Semi-automatic USDJPY basket assistant: proposes, you click; it manages."

#include <Trade\Trade.mqh>

//--- inputs
input group "Account / challenge"
input double InpAccountStart    = 10000.0;  // Account start balance (phase start)
input double InpTargetPct       = 10.0;     // Phase profit target % (10 phase 1, 5 phase 2)
input double InpDailyLossPct    = 5.0;      // Firm daily loss limit % (equity vs day-start balance)
input double InpMaxLossPct      = 10.0;     // Firm max loss % (static, from account start)
input double InpDailyGuardPct   = 4.0;      // Block entries when today's loss incl. floating >= this %
input double InpBudgetPct       = 4.6;      // Block an entry if every stop hitting would push today's loss past this %
input double InpMaxGuardPct     = 9.0;      // Block entries when total loss (now or at the stops) >= this %
input double InpMaxLots         = 5.0;      // Hard cap per order
input double InpCommissionPerLot= 7.0;      // Commission per lot round turn, account currency (budget only)
input double InpSlipCostPips    = 1.0;      // Slippage allowance per trade, pips (budget only)
input group "Risk per trade (% of balance)"
input double InpRiskBox         = 0.25;     // Box breakout
input double InpRiskGotobi      = 3.6;      // Gotobi short (3.6 keeps the 4.6% budget from blocking it next to a box trade)
input double InpRiskM3          = 3.6;      // Month-end USD bid
input bool   InpProtect         = true;     // Halve every risk while balance < 97% of account start
input group "Vol filter"
input bool   InpVolFilter       = true;     // Box and gotobi only when ATR20 >= 250-day median
input int    InpAtrDays         = 20;       // ATR window (daily high-low, previous days)
input int    InpMedianDays      = 250;      // Median window of ATR20 (filter OFF while history is shorter)
input group "Box breakout (Version B)"
input bool   InpBoxOn           = true;
input string InpBoxStartUTC     = "23:30";  // Box start UTC (05:00 IST)
input int    InpBoxMinutes      = 60;       // Box length in minutes
input string InpBoxPlaceUTC     = "00:30";  // Order placement UTC (06:00 IST)
input string InpBoxExpiryUTC    = "05:30";  // Orders expire UTC (11:00 IST)
input int    InpBoxMinBars      = 60;       // Minimum M1 bars inside the box (backtest: all 60)
input int    InpBoxDataWaitMin  = 10;       // Minutes to wait for the last box bar before deciding
input double InpBoxRR           = 9.0;      // Take profit in R
input double InpBoxBeTriggerR   = 3.0;      // Move stop at +R
input double InpBoxBeOffsetDiv  = 6.0;      // Moved stop = entry + box / this
input int    InpReentryWaitMin  = 6;        // Minutes after a stop-out before the re-entry stop
input group "Gotobi fix short"
input bool   InpGotobiOn        = true;
input string InpGotobiEntryUTC  = "00:55";  // Entry UTC (09:55 Tokyo)
input string InpGotobiExitUTC   = "06:00";  // Time exit UTC
input double InpGotobiSlAtr     = 0.25;     // Stop in ATR20
input group "Month-end USD bid (M-3)"
input bool   InpM3On            = true;
input string InpM3EntryUTC      = "11:00";  // Entry UTC
input string InpM3ExitUTC       = "12:00";  // Time exit UTC
input double InpM3SlAtr         = 0.25;     // Stop in ATR20
input group "Execution"
input int    InpSignalWindowMin = 10;       // Minutes a market signal stays clickable
input int    InpDeviationPts    = 30;       // Max slippage in points for market orders
input long   InpMagicBox        = 241001;
input long   InpMagicGotobi     = 241002;
input long   InpMagicM3         = 241003;
input int    InpPanelX          = 10;
input int    InpPanelY          = 25;
input int    InpFontSize        = 9;

//--- constants
#define PFX          "ABA_"
#define BTN_BOX      "ABA_BTN_BOX"
#define BTN_BOX_SKIP "ABA_BTN_BOX_SKIP"
#define BTN_TM       "ABA_BTN_TIMED"
#define BTN_TM_SKIP  "ABA_BTN_TIMED_SKIP"
#define LOG_FILE     "ABA_log.csv"

enum ACTION { ACT_NONE = 0, ACT_BOX, ACT_REENTRY, ACT_GOTOBI, ACT_M3 };
enum SKIP   { SKIP_NONE = 0, SKIP_DISABLED, SKIP_WEEKEND, SKIP_NOBOX, SKIP_BARS, SKIP_VOL };

// today's box activity, rebuilt from the deal history on every update
struct BoxToday
  {
   int      trades;        // distinct box positions opened since today's placement time
   ulong    openPos;       // ticket of the last of them if still open
   int      lastSide;      // +1 / -1 of the last one
   bool     lastClosed;
   datetime lastCloseUtc;
   long     lastReason;
   double   lastClosePx;
  };

//--- state
CTrade   g_trade;
string   g_key;                 // global-variable prefix: PFX + login + symbol
double   g_pip, g_point;
int      g_digits;
int      g_offSec;              // server time minus UTC, seconds
bool     g_offOk = true;        // offset is a whole 2 or 3 hours
bool     g_clockOk = true;      // PC clock agrees with the server ticks
string   g_failKeys[16];        // rate-limit memory for LogFail
datetime g_failTimes[16];
int      g_failNext = 0;
ulong    g_reTicket = 0;        // ticket of the re-entry order placed today (persisted)
datetime g_todayUtc;
double   g_dayStart, g_realisedToday;
double   g_atr20, g_median;
int      g_histBars;
bool     g_volOn;
string   g_msg = "";
datetime g_lastFailLog = 0;
BoxToday g_bt;
ACTION   g_actBox = ACT_NONE, g_actTimed = ACT_NONE;        // proposals computed by Update()
datetime g_actBoxUntil = 0, g_actTimedUntil = 0;
ACTION   g_drawnBox = ACT_NONE, g_drawnTimed = ACT_NONE;    // what the buttons showed last
int      g_reSide = 0;
double   g_reLvl = 0;
datetime g_reAt = 0;

// box day state (persisted)
datetime g_boxDay = 0;          // UTC date of the placement
double   g_boxHi = 0, g_boxLo = 0;
int      g_boxBars = 0;
int      g_boxSkipCode = SKIP_NONE;
bool     g_boxPlaced = false;
double   g_boxRisk = 0;         // stop distance used for today's orders (fallback when a comment lacks r=)
bool     g_boxDismissed = false;
bool     g_reentryPlaced = false;
string   g_boxNote = "";

// gotobi / m3 (persisted)
datetime g_gotobiDay = 0;
bool     g_gotobiTaken = false, g_gotobiDismissed = false;
double   g_gotobiRisk = 0;
datetime g_m3Day = 0;
bool     g_m3Taken = false, g_m3Dismissed = false;
double   g_m3Risk = 0;

//+------------------------------------------------------------------+
//| time helpers                                                      |
//+------------------------------------------------------------------+
int ParseHHMM(const string s)
  {
   string parts[];
   if(StringSplit(s, ':', parts) < 2) return -1;
   int hh = (int)StringToInteger(parts[0]), mm = (int)StringToInteger(parts[1]);
   if(hh < 0 || hh > 23 || mm < 0 || mm > 59) return -1;
   return hh * 3600 + mm * 60;
  }
datetime UtcNow() { return TimeGMT(); }
datetime DateOf(const datetime t) { return t - (t % 86400); }
int      SecOfDay(const datetime t) { return (int)(t % 86400); }
int      DayOfWeek(const datetime t) { MqlDateTime st; TimeToStruct(t, st); return st.day_of_week; }
bool     IsWeekday(const datetime d) { int w = DayOfWeek(d); return (w >= 1 && w <= 5); }
datetime ToServer(const datetime utc) { return utc + g_offSec; }
datetime ToUtc(const datetime srv) { return srv - g_offSec; }
string   Hm(const datetime t) { return TimeToString(t, TIME_MINUTES); }
string   Dmy(const datetime t) { return TimeToString(t, TIME_DATE); }
string   Tk(const ulong t) { return IntegerToString((long)t); }

void UpdateOffset()
  {
   double diff = (double)(TimeTradeServer() - TimeGMT());
   g_offSec = (int)(MathRound(diff / 1800.0) * 1800.0);
   g_offOk = (g_offSec == 2 * 3600 || g_offSec == 3 * 3600);
   // a wrong PC clock shifts TimeGMT and TimeTradeServer together; the last tick time (TimeCurrent) does not move with it
   datetime srvEst = TimeTradeServer(), lastTick = TimeCurrent();
   g_clockOk = true;
   if(lastTick > srvEst + 60) g_clockOk = false;                        // a tick from the future: the PC clock is behind
   else
     {
      MqlDateTime st; TimeToStruct(srvEst, st);
      int s = st.hour * 3600 + st.min * 60 + st.sec;
      bool inSession = (st.day_of_week >= 1 && st.day_of_week <= 5 && s >= 10 * 60 + 300 && s <= 23 * 3600 + 50 * 60);
      if(inSession && srvEst > lastTick + 300) g_clockOk = false;        // no tick for 5 minutes inside the session: clock ahead or feed dead
     }
  }

int DaysInMonth(const int year, const int month)
  {
   static const int dm[12] = {31,28,31,30,31,30,31,31,30,31,30,31};
   if(month == 2) return (((year % 4 == 0 && year % 100 != 0) || year % 400 == 0) ? 29 : 28);
   return dm[month - 1];
  }

datetime MakeDate(const int year, const int month, const int day)
  {
   MqlDateTime st; ZeroMemory(st);
   st.year = year; st.mon = month; st.day = day;
   return StructToTime(st);
  }

bool IsGotobiDate(const datetime d)
  {
   MqlDateTime st; TimeToStruct(d, st);
   int targets[6] = {5, 10, 15, 20, 25, 0};
   targets[5] = DaysInMonth(st.year, st.mon);
   for(int i = 0; i < 6; i++)
     {
      datetime t = MakeDate(st.year, st.mon, targets[i]);
      while(DayOfWeek(t) == 0 || DayOfWeek(t) == 6) t -= 86400;
      if(t == DateOf(d)) return true;
     }
   return false;
  }

bool IsM3Date(const datetime d)
  {
   if(!IsWeekday(d)) return false;
   MqlDateTime st; TimeToStruct(d, st);
   int last = DaysInMonth(st.year, st.mon), left = 0;
   for(int k = st.day + 1; k <= last; k++) if(IsWeekday(MakeDate(st.year, st.mon, k))) left++;
   return (left == 2);
  }

datetime NextDate(const datetime from, const bool gotobi)
  {
   datetime d = DateOf(from);
   for(int i = 0; i < 45; i++, d += 86400) if(gotobi ? IsGotobiDate(d) : IsM3Date(d)) return d;
   return 0;
  }

//+------------------------------------------------------------------+
//| logging and panel primitives                                      |
//+------------------------------------------------------------------+
void Log(const string ev, const string det)
  {
   string line = TimeToString(UtcNow(), TIME_DATE | TIME_SECONDS) + " UTC | " + ev + " | " + det;
   Print(line);
   g_msg = ev + ": " + det;
   int h = FileOpen(LOG_FILE, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h != INVALID_HANDLE) { FileSeek(h, 0, SEEK_END); FileWriteString(h, line + "\r\n"); FileClose(h); }
  }

// failures that can repeat every tick: at most one log line a minute per event and ticket
void LogFail(const string ev, const string det)
  {
   datetime now = UtcNow();
   string key = ev + "|" + det;
   for(int i = 0; i < 16; i++)
      if(g_failKeys[i] == key && now - g_failTimes[i] < 60) { g_msg = ev + ": " + det; return; }
   g_failKeys[g_failNext] = key; g_failTimes[g_failNext] = now; g_failNext = (g_failNext + 1) % 16;
   Log(ev, det);
  }

// ---- colours of the dashboard
#define C_BG      C'24,27,34'
#define C_CARD    C'33,38,48'
#define C_HEAD    C'44,52,66'
#define C_LINE    C'70,78,94'
#define C_DIM     C'150,158,172'
#define C_TXT     C'230,233,238'
#define C_OK      C'46,160,96'
#define C_WARN    C'230,150,40'
#define C_BAD     C'205,62,55'
#define C_INFO    C'60,120,200'
#define C_IDLE    C'90,98,112'

string FontText() { return "Segoe UI"; }
string FontHead() { return "Segoe UI Semibold"; }
string FontMono() { return "Consolas"; }

void Rect(const string name, const int x, const int y, const int w, const int h, const color bg, const color border)
  {
   if(ObjectFind(0, name) < 0)
     {
      ObjectCreate(0, name, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, false);
     }
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, name, OBJPROP_YSIZE, h);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR, bg);
   ObjectSetInteger(0, name, OBJPROP_COLOR, border);
  }

void Text(const string name, const int x, const int y, const string text, const color clr, const int size, const string font)
  {
   if(ObjectFind(0, name) < 0)
     {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
     }
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetString(0, name, OBJPROP_TEXT, text == "" ? " " : text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, size);
   ObjectSetString(0, name, OBJPROP_FONT, font);
  }

void Button(const string name, const int x, const int y, const int w, const int h, const string text, const color bg, const color fg = clrWhite)
  {
   if(ObjectFind(0, name) < 0)
     {
      ObjectCreate(0, name, OBJ_BUTTON, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, InpFontSize + 1);
      ObjectSetString(0, name, OBJPROP_FONT, FontHead());
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BORDER_COLOR, C_LINE);
     }
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, name, OBJPROP_YSIZE, h);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR, bg);
   ObjectSetInteger(0, name, OBJPROP_COLOR, fg);
   ObjectSetInteger(0, name, OBJPROP_STATE, false);
  }

// a card: body rectangle, header strip, title
void Card(const string id, const int x, const int y, const int w, const int h, const string title)
  {
   Rect(PFX + id + "_bg", x, y, w, h, C_CARD, C_LINE);
   Rect(PFX + id + "_hd", x, y, w, 20, C_HEAD, C_HEAD);
   Text(PFX + id + "_tt", x + 8, y + 2, title, C_TXT, InpFontSize, FontHead());
  }

// a coloured status pill with centred-ish text
void Pill(const string id, const int x, const int y, const int w, const string text, const color bg)
  {
   Rect(PFX + id + "_pb", x, y, w, 18, bg, bg);
   Text(PFX + id + "_pt", x + 7, y + 1, text, clrWhite, InpFontSize, FontHead());
  }

// a horizontal bar: frac in 0..1 of the width
void Bar(const string id, const int x, const int y, const int w, const double frac, const color fill)
  {
   Rect(PFX + id + "_bb", x, y, w, 8, C'18,20,26', C_LINE);
   int fw = (int)MathRound(MathMin(MathMax(frac, 0.0), 1.0) * (w - 2));
   Rect(PFX + id + "_bf", x + 1, y + 1, MathMax(fw, 1), 6, fw > 0 ? fill : C'18,20,26', fw > 0 ? fill : C'18,20,26');
  }

// key on the left (dim), value on the right (bright)
void KV(const string id, const int x, const int y, const int w, const string key, const string val, const color vclr = C_TXT)
  {
   Text(PFX + id + "_k", x, y, key, C_DIM, InpFontSize, FontText());
   Text(PFX + id + "_v", x + w, y, val, vclr, InpFontSize, FontText());
  }

string Fit(const string s, const int maxChars)
  {
   if(StringLen(s) <= maxChars) return s;
   return StringSubstr(s, 0, maxChars - 3) + "...";
  }

// ---- layout
#define PANEL_W  880
#define GAP      8
#define CARD_W   288      // (880 - 2*8 - 2*8) / 3
int LayY(const int row)   // top of each band
  {
   int y = InpPanelY;
   if(row >= 1) y += 30;           // after the title bar
   if(row >= 2) y += 104 + GAP;    // after the top cards
   if(row >= 3) y += 124 + GAP;    // after the leg cards
   if(row >= 4) y += 92 + GAP;     // after the positions card
   if(row >= 5) y += 72;           // after the buttons
   return y;
  }
int PanelH() { return LayY(5) + 22 - InpPanelY; }
int ButtonsY() { return LayY(4); }

void CreatePanel()
  {
   Rect(PFX + "BG", InpPanelX, InpPanelY, PANEL_W, PanelH(), C_BG, C_LINE);
   Button(BTN_BOX, InpPanelX + GAP, ButtonsY(), 600, 30, "box: no signal", C_IDLE);
   Button(BTN_BOX_SKIP, InpPanelX + GAP + 612, ButtonsY(), 252, 30, "-", C_IDLE);
   Button(BTN_TM, InpPanelX + GAP, ButtonsY() + 38, 600, 30, "gotobi / M-3: no signal", C_IDLE);
   Button(BTN_TM_SKIP, InpPanelX + GAP + 612, ButtonsY() + 38, 252, 30, "-", C_IDLE);
  }

//+------------------------------------------------------------------+
//| market data and account                                           |
//+------------------------------------------------------------------+
double Pips(const double priceDist) { return priceDist / g_pip; }
double Spread() { return SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID); }

void UpdateAtr()
  {
   int need = InpAtrDays + InpMedianDays;
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_D1, 1, need, r);      // oldest first; the last element is yesterday's bar
   g_histBars = (n > 0) ? n : 0;
   g_atr20 = 0; g_median = 0; g_volOn = false;
   if(n < InpAtrDays) return;
   int cnt = n - InpAtrDays + 1;
   double atr[]; ArrayResize(atr, cnt);
   double s = 0;
   for(int i = 0; i < InpAtrDays; i++) s += r[i].high - r[i].low;
   atr[0] = s / InpAtrDays;
   for(int e = InpAtrDays; e < n; e++)
     {
      s += (r[e].high - r[e].low) - (r[e - InpAtrDays].high - r[e - InpAtrDays].low);
      atr[e - InpAtrDays + 1] = s / InpAtrDays;
     }
   g_atr20 = atr[cnt - 1];
   int m = MathMin(InpMedianDays, cnt);
   double w[]; ArrayResize(w, m);
   for(int i = 0; i < m; i++) w[i] = atr[cnt - m + i];
   ArraySort(w);
   g_median = (m % 2 == 1) ? w[m / 2] : 0.5 * (w[m / 2 - 1] + w[m / 2]);
   if(!InpVolFilter) g_volOn = true;
   else g_volOn = (cnt >= InpMedianDays) && (g_atr20 >= g_median);   // reference: median needs the full window
  }

void UpdateDayStart()
  {
   datetime srvNow = TimeTradeServer();
   datetime srvMidnight = DateOf(srvNow);
   double closed = 0;
   if(HistorySelect(srvMidnight, srvNow + 3600))
     {
      int n = HistoryDealsTotal();
      for(int i = 0; i < n; i++)
        {
         ulong d = HistoryDealGetTicket(i);
         if(d == 0 || HistoryDealGetString(d, DEAL_SYMBOL) == "") continue;
         closed += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_SWAP) + HistoryDealGetDouble(d, DEAL_COMMISSION) + HistoryDealGetDouble(d, DEAL_FEE);
        }
     }
   g_realisedToday = closed;
   g_dayStart = AccountInfoDouble(ACCOUNT_BALANCE) - closed;
  }

double Equity() { return AccountInfoDouble(ACCOUNT_EQUITY); }
double Balance() { return AccountInfoDouble(ACCOUNT_BALANCE); }
double DailyUsedPct() { return g_dayStart > 0 ? 100.0 * (g_dayStart - Equity()) / g_dayStart : 0; }
double MaxUsedPct() { return InpAccountStart > 0 ? 100.0 * (InpAccountStart - Equity()) / InpAccountStart : 0; }
bool   ProtectActive() { return InpProtect && Balance() < 0.97 * InpAccountStart; }

double TickValueLoss(const string sym) { return SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE_LOSS); }
double TickSize(const string sym) { return SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE); }

double LossAtStop(const double lots, const double dist)
  {
   double ts = TickSize(_Symbol), tv = TickValueLoss(_Symbol);
   if(ts <= 0 || tv <= 0) return 0;
   return lots * dist / ts * tv;
  }

double TradeCosts(const double lots) { return lots * InpCommissionPerLot + LossAtStop(lots, InpSlipCostPips * g_pip); }

double LotsForRisk(const double riskPct, const double dist)
  {
   if(dist <= 0) return 0;
   double pct = riskPct * (ProtectActive() ? 0.5 : 1.0);
   double riskUsd = Balance() * pct / 100.0;
   double perLot = LossAtStop(1.0, dist);
   if(perLot <= 0) return 0;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = MathMin(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX), InpMaxLots);
   if(step <= 0) step = 0.01;
   double lots = MathFloor(riskUsd / perLot / step + 1e-9) * step;
   if(lots < vmin) return 0;
   if(lots > vmax) lots = vmax;
   return NormalizeDouble(lots, 2);
  }

// P/L in account currency if a position's stop is hit (negative = loss); false when it has no stop
bool PositionPlAtStop(double &pl)
  {
   double sl = PositionGetDouble(POSITION_SL), op = PositionGetDouble(POSITION_PRICE_OPEN), vol = PositionGetDouble(POSITION_VOLUME);
   string sym = PositionGetString(POSITION_SYMBOL);
   pl = PositionGetDouble(POSITION_SWAP);
   if(sl <= 0) return false;
   long type = PositionGetInteger(POSITION_TYPE);
   double move = (type == POSITION_TYPE_BUY) ? (sl - op) : (op - sl);   // negative for a loss
   double ts = TickSize(sym), tv = TickValueLoss(sym);
   if(ts > 0 && tv > 0) pl += vol * move / ts * tv;
   return true;
  }

// worst-case equity if every stop is hit: all positions, the larger side of the working box pair, and the new trade
double WorstCaseEquity(const double newLots, const double newDist, bool &unbounded)
  {
   unbounded = false;
   double eq = Balance();
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || !PositionSelectByTicket(t)) continue;
      double pl;
      if(!PositionPlAtStop(pl)) { unbounded = true; continue; }
      eq += MathMin(pl, 0.0);
     }
   double worstOrder = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t == 0 || !OrderSelect(t) || OrderGetInteger(ORDER_MAGIC) != InpMagicBox || OrderGetString(ORDER_SYMBOL) != _Symbol) continue;
      double sl = OrderGetDouble(ORDER_SL), px = OrderGetDouble(ORDER_PRICE_OPEN), vol = OrderGetDouble(ORDER_VOLUME_CURRENT);
      if(sl <= 0) { unbounded = true; continue; }
      worstOrder = MathMax(worstOrder, LossAtStop(vol, MathAbs(px - sl)) + TradeCosts(vol));
     }
   eq -= worstOrder;
   if(newLots > 0) eq -= LossAtStop(newLots, newDist) + TradeCosts(newLots);
   return eq;
  }

bool GuardsAllow(const double lots, const double dist, string &why)
  {
   why = "";
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED)) { why = "AutoTrading is off in the terminal"; return false; }
   if(!g_offOk) { why = StringFormat("server offset %+.1f h is not 2 or 3: check the PC clock", g_offSec / 3600.0); return false; }
   if(!g_clockOk) { why = "PC clock disagrees with the server ticks (or the feed is dead)"; return false; }
   if(lots <= 0) { why = "lot below the minimum for this stop"; return false; }
   if(DailyUsedPct() >= InpDailyGuardPct) { why = StringFormat("daily guard: %.2f%% used of %.1f%%", DailyUsedPct(), InpDailyGuardPct); return false; }
   if(MaxUsedPct() >= InpMaxGuardPct) { why = StringFormat("max-loss guard: %.2f%% used of %.1f%%", MaxUsedPct(), InpMaxGuardPct); return false; }
   bool unb;
   double wEq = WorstCaseEquity(lots, dist, unb);
   if(unb) { why = "a position or order without a stop is open"; return false; }
   double dWorst = (g_dayStart > 0) ? 100.0 * (g_dayStart - wEq) / g_dayStart : 0;
   double mWorst = (InpAccountStart > 0) ? 100.0 * (InpAccountStart - wEq) / InpAccountStart : 0;
   if(dWorst > InpBudgetPct) { why = StringFormat("daily budget: %.2f%% at the stops > %.1f%%", dWorst, InpBudgetPct); return false; }
   if(mWorst > InpMaxGuardPct) { why = StringFormat("max-loss budget: %.2f%% at the stops > %.1f%%", mWorst, InpMaxGuardPct); return false; }
   double margin = 0;
   if(OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, lots, SymbolInfoDouble(_Symbol, SYMBOL_ASK), margin))
      if(margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE)) { why = StringFormat("margin %.0f needed, %.0f free", margin, AccountInfoDouble(ACCOUNT_MARGIN_FREE)); return false; }
   return true;
  }

bool IsOurs(const long magic) { return (PositionGetInteger(POSITION_MAGIC) == magic && PositionGetString(POSITION_SYMBOL) == _Symbol); }

int CountPositions(const long magic)
  {
   int c = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--) { ulong t = PositionGetTicket(i); if(t != 0 && PositionSelectByTicket(t) && IsOurs(magic)) c++; }
   return c;
  }

ulong FirstPosition(const long magic)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--) { ulong t = PositionGetTicket(i); if(t != 0 && PositionSelectByTicket(t) && IsOurs(magic)) return t; }
   return 0;
  }

ulong PositionByIdentifier(const long posId)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     { ulong t = PositionGetTicket(i); if(t != 0 && PositionSelectByTicket(t) && PositionGetInteger(POSITION_IDENTIFIER) == posId) return t; }
   return 0;
  }

bool IsBoxOrder(const ulong t) { return OrderSelect(t) && OrderGetInteger(ORDER_MAGIC) == InpMagicBox && OrderGetString(ORDER_SYMBOL) == _Symbol; }

int CountBoxOrders()
  {
   int c = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--) { ulong t = OrderGetTicket(i); if(t != 0 && IsBoxOrder(t)) c++; }
   return c;
  }

// box orders set up at or after today's placement time
int CountBoxOrdersToday()
  {
   int c = 0;
   if(g_boxDay == 0) return 0;
   datetime fromSrv = ToServer(g_boxDay + ParseHHMM(InpBoxPlaceUTC));
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     { ulong t = OrderGetTicket(i); if(t != 0 && IsBoxOrder(t) && (datetime)OrderGetInteger(ORDER_TIME_SETUP) >= fromSrv) c++; }
   return c;
  }

// delete every box order except `keep` (0 = all)
void DeleteBoxOrders(const ulong keep, const string reason)
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t == 0 || !IsBoxOrder(t) || t == keep) continue;
      if(g_trade.OrderDelete(t)) Log("order deleted", reason + " #" + Tk(t));
      else LogFail("order delete FAILED", reason + " #" + Tk(t) + " " + g_trade.ResultRetcodeDescription());
     }
  }

// box orders whose own expiry (05:30 UTC of their setup day) has passed, whatever day it is now
void DeleteStaleBoxOrders()
  {
   if(!g_clockOk) return;                 // never act on timing while the clock is suspect
   int expSec = ParseHHMM(InpBoxExpiryUTC);
   datetime now = UtcNow();
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t == 0 || !IsBoxOrder(t)) continue;
      datetime setupUtc = ToUtc((datetime)OrderGetInteger(ORDER_TIME_SETUP));
      if(now >= DateOf(setupUtc) + expSec)
        {
         if(g_trade.OrderDelete(t)) Log("order deleted", "expired #" + Tk(t) + " set up " + TimeToString(setupUtc, TIME_DATE | TIME_MINUTES) + " UTC");
         else LogFail("order delete FAILED", "expired #" + Tk(t) + " " + g_trade.ResultRetcodeDescription());
        }
     }
  }

void ClosePositionsByTime(const long magic, const int exitSec, const string tag)
  {
   if(!g_clockOk) return;                 // never act on timing while the clock is suspect
   datetime now = UtcNow();
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || !PositionSelectByTicket(t) || !IsOurs(magic)) continue;
      datetime openUtc = ToUtc((datetime)PositionGetInteger(POSITION_TIME));
      if(now < DateOf(openUtc) + exitSec) continue;
      g_trade.SetExpertMagicNumber(magic);
      if(g_trade.PositionClose(t, InpDeviationPts)) Log("position closed", tag + " time exit #" + Tk(t));
      else LogFail("position close FAILED", tag + " #" + Tk(t) + " " + g_trade.ResultRetcodeDescription());
      g_trade.SetExpertMagicNumber(InpMagicBox);
     }
  }

//+------------------------------------------------------------------+
//| persistence                                                       |
//+------------------------------------------------------------------+
void GVSet(const string k, const double v) { GlobalVariableSet(g_key + k, v); }
double GV(const string k, const double def = 0) { return GlobalVariableCheck(g_key + k) ? GlobalVariableGet(g_key + k) : def; }

void SaveState()
  {
   GVSet("boxDay", (double)g_boxDay); GVSet("boxHi", g_boxHi); GVSet("boxLo", g_boxLo); GVSet("boxBars", g_boxBars);
   GVSet("boxSkip", g_boxSkipCode); GVSet("boxPlaced", g_boxPlaced ? 1 : 0); GVSet("boxRisk", g_boxRisk);
   GVSet("boxDismissed", g_boxDismissed ? 1 : 0); GVSet("rePlaced", g_reentryPlaced ? 1 : 0); GVSet("reTicket", (double)g_reTicket);
   GVSet("gDay", (double)g_gotobiDay); GVSet("gTaken", g_gotobiTaken ? 1 : 0); GVSet("gDism", g_gotobiDismissed ? 1 : 0); GVSet("gRisk", g_gotobiRisk);
   GVSet("mDay", (double)g_m3Day); GVSet("mTaken", g_m3Taken ? 1 : 0); GVSet("mDism", g_m3Dismissed ? 1 : 0); GVSet("mRisk", g_m3Risk);
   GlobalVariablesFlush();
  }

void LoadState()
  {
   g_boxDay = (datetime)GV("boxDay"); g_boxHi = GV("boxHi"); g_boxLo = GV("boxLo"); g_boxBars = (int)GV("boxBars");
   g_boxSkipCode = (int)GV("boxSkip"); g_boxPlaced = GV("boxPlaced") > 0; g_boxRisk = GV("boxRisk");
   g_boxDismissed = GV("boxDismissed") > 0; g_reentryPlaced = GV("rePlaced") > 0; g_reTicket = (ulong)GV("reTicket");
   g_gotobiDay = (datetime)GV("gDay"); g_gotobiTaken = GV("gTaken") > 0; g_gotobiDismissed = GV("gDism") > 0; g_gotobiRisk = GV("gRisk");
   g_m3Day = (datetime)GV("mDay"); g_m3Taken = GV("mTaken") > 0; g_m3Dismissed = GV("mDism") > 0; g_m3Risk = GV("mRisk");
  }

string SkipText(const int code)
  {
   switch(code)
     {
      case SKIP_DISABLED: return "box leg disabled";
      case SKIP_WEEKEND:  return "weekend";
      case SKIP_NOBOX:    return "no box: flat or no bars";
      case SKIP_BARS:     return StringFormat("only %d M1 bars in the box (min %d)", g_boxBars, InpBoxMinBars);
      case SKIP_VOL:      return "vol filter OFF";
     }
   return "";
  }

//+------------------------------------------------------------------+
//| box: build the box, read today's activity from history            |
//+------------------------------------------------------------------+
datetime BoxStartUtc(const datetime placeDate)
  {
   int startSec = ParseHHMM(InpBoxStartUTC), placeSec = ParseHHMM(InpBoxPlaceUTC);
   datetime startDate = (startSec > placeSec) ? placeDate - 86400 : placeDate;
   return startDate + startSec;
  }

// fills hi/lo/bars; lastBarOk says the final box minute has been received
bool BuildBox(const datetime placeDate, bool &lastBarOk)
  {
   datetime startUtc = BoxStartUtc(placeDate), endUtc = startUtc + InpBoxMinutes * 60 - 60;
   MqlRates rates[];
   int n = CopyRates(_Symbol, PERIOD_M1, ToServer(startUtc), ToServer(endUtc), rates);
   g_boxBars = (n > 0) ? n : 0;
   g_boxHi = 0; g_boxLo = 0; lastBarOk = false;
   if(n <= 0) return false;
   double hi = -1, lo = 1e9;
   for(int i = 0; i < n; i++) { if(rates[i].high > hi) hi = rates[i].high; if(rates[i].low < lo) lo = rates[i].low; }
   g_boxHi = hi; g_boxLo = lo;
   lastBarOk = (rates[n - 1].time == ToServer(endUtc));
   return (hi > lo);
  }

// true when the day is decided (box built and skip reason set); false while still waiting for data
bool StartBoxDay(const datetime placeDate)
  {
   int placeSec = ParseHHMM(InpBoxPlaceUTC);
   datetime placeSrv = ToServer(placeDate + placeSec);
   if(TimeCurrent() < placeSrv) return false;                          // server clock, not the PC clock
   bool lastOk;
   bool ok = BuildBox(placeDate, lastOk);
   bool dataComplete = lastOk && g_boxBars >= InpBoxMinutes && g_histBars >= InpAtrDays + InpMedianDays - 1;
   if(!dataComplete && TimeCurrent() < placeSrv + InpBoxDataWaitMin * 60 && IsWeekday(placeDate) && InpBoxOn)
     { g_boxNote = StringFormat("waiting for data (%d bars, last bar %s, D1 bars %d)", g_boxBars, lastOk ? "ok" : "missing", g_histBars); return false; }
   g_boxDay = placeDate;
   g_boxPlaced = false; g_boxRisk = 0; g_boxDismissed = false; g_reentryPlaced = false; g_reTicket = 0; g_boxNote = "";
   g_boxSkipCode = SKIP_NONE;
   if(!InpBoxOn) g_boxSkipCode = SKIP_DISABLED;
   else if(!IsWeekday(placeDate)) g_boxSkipCode = SKIP_WEEKEND;
   else if(!ok) g_boxSkipCode = SKIP_NOBOX;
   else if(g_boxBars < InpBoxMinBars) g_boxSkipCode = SKIP_BARS;
   else if(!g_volOn) g_boxSkipCode = SKIP_VOL;
   Log("box day", StringFormat("%s hi %.3f lo %.3f (%.1f pips) bars %d %s", Dmy(placeDate), g_boxHi, g_boxLo, Pips(g_boxHi - g_boxLo), g_boxBars, SkipText(g_boxSkipCode)));
   SaveState();
   return true;
  }

void BoxTodayStats(BoxToday &b)
  {
   b.trades = 0; b.openPos = 0; b.lastSide = 0; b.lastClosed = false; b.lastCloseUtc = 0; b.lastReason = -1; b.lastClosePx = 0;
   if(g_boxDay == 0) return;
   datetime fromSrv = ToServer(g_boxDay + ParseHHMM(InpBoxPlaceUTC));
   if(!HistorySelect(fromSrv, TimeTradeServer() + 3600)) return;
   long ids[]; int nIds = 0;
   long lastPosId = 0; datetime lastIn = 0;
   int n = HistoryDealsTotal();
   for(int i = 0; i < n; i++)
     {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0 || HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagicBox || HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol) continue;
      if(HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_IN) continue;
      long pid = HistoryDealGetInteger(d, DEAL_POSITION_ID);
      bool seen = false;
      for(int k = 0; k < nIds; k++) if(ids[k] == pid) { seen = true; break; }
      if(!seen) { ArrayResize(ids, nIds + 1); ids[nIds++] = pid; }
      datetime tm = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
      if(tm >= lastIn) { lastIn = tm; lastPosId = pid; b.lastSide = (HistoryDealGetInteger(d, DEAL_TYPE) == DEAL_TYPE_BUY) ? 1 : -1; }
     }
   b.trades = nIds;
   if(lastPosId == 0) return;
   b.openPos = PositionByIdentifier(lastPosId);
   if(b.openPos != 0) return;
   for(int i = 0; i < n; i++)
     {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0 || HistoryDealGetInteger(d, DEAL_POSITION_ID) != lastPosId) continue;
      long en = HistoryDealGetInteger(d, DEAL_ENTRY);
      if(en != DEAL_ENTRY_OUT && en != DEAL_ENTRY_OUT_BY) continue;
      b.lastClosed = true;
      b.lastCloseUtc = ToUtc((datetime)HistoryDealGetInteger(d, DEAL_TIME));
      b.lastReason = HistoryDealGetInteger(d, DEAL_REASON);
      b.lastClosePx = HistoryDealGetDouble(d, DEAL_PRICE);
     }
  }

double FromComment(const string comment, const string tag, const double fallback)
  {
   int p = StringFind(comment, tag);
   if(p < 0) return fallback;
   double v = StringToDouble(StringSubstr(comment, p + StringLen(tag)));
   return (v > 0) ? v : fallback;
  }

// has price touched the box high (ask, if checkHi) or low (bid, if checkLo) since fromUtc? Scans from the minute containing fromUtc.
bool LevelTouchedSince(const datetime fromUtc, const bool checkHi, const bool checkLo, datetime &when)
  {
   when = 0;
   MqlRates rates[];
   datetime from = fromUtc - (fromUtc % 60);
   int n = CopyRates(_Symbol, PERIOD_M1, ToServer(from), TimeTradeServer() + 60, rates);
   double sp = Spread();
   for(int i = 0; i < n; i++)
     {
      double barSpread = (rates[i].spread > 0) ? rates[i].spread * g_point : sp;   // M1 bars are bid; the buy stop triggers on the ask
      if((checkHi && rates[i].high + barSpread >= g_boxHi) || (checkLo && rates[i].low <= g_boxLo)) { when = ToUtc(rates[i].time); return true; }
     }
   return false;
  }

// all the conditions a click must satisfy before any box order goes out
bool BoxPreflight(const double risk, string &why)
  {
   why = "";
   if(g_boxDay != g_todayUtc) why = "no box for today";
   else if(g_boxSkipCode != SKIP_NONE) why = "box skipped today: " + SkipText(g_boxSkipCode);
   else if(!IsWeekday(g_todayUtc)) why = "weekend";
   else if(g_boxBars < InpBoxMinBars || g_boxHi <= g_boxLo) why = "box data incomplete";
   else if(InpVolFilter && !g_volOn) why = "vol filter OFF";
   else if(risk < MathMax(3 * g_pip, 3 * Spread())) why = StringFormat("stop %.1f pips too small", Pips(risk));
   return (why == "");
  }

//+------------------------------------------------------------------+
//| actions (only from the PLACE buttons)                             |
//+------------------------------------------------------------------+
bool PlaceStop(const bool buy, const double lots, const double level, const double sl, const double tp, const datetime expirySrv, const string comment)
  {
   bool ok = buy ? g_trade.BuyStop(lots, level, _Symbol, sl, tp, ORDER_TIME_SPECIFIED, expirySrv, comment)
                 : g_trade.SellStop(lots, level, _Symbol, sl, tp, ORDER_TIME_SPECIFIED, expirySrv, comment);
   if(!ok && g_trade.ResultRetcode() == TRADE_RETCODE_INVALID_EXPIRATION)
     {
      Log("stop order retry as GTC", "broker refused the expiration; the EA deletes it at 05:30 UTC itself");
      ok = buy ? g_trade.BuyStop(lots, level, _Symbol, sl, tp, ORDER_TIME_GTC, 0, comment)
               : g_trade.SellStop(lots, level, _Symbol, sl, tp, ORDER_TIME_GTC, 0, comment);
     }
   return ok;
  }

bool MarketBox(const int side, const double lots, const double risk, const string cm)
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   bool ok = (side > 0) ? g_trade.Buy(lots, _Symbol, 0, NormalizeDouble(ask - risk, g_digits), NormalizeDouble(ask + InpBoxRR * risk, g_digits), cm)
                        : g_trade.Sell(lots, _Symbol, 0, NormalizeDouble(bid + risk, g_digits), NormalizeDouble(bid - InpBoxRR * risk, g_digits), cm);
   Log(ok ? "box market order" : "box market order FAILED", StringFormat("%s lots %.2f risk %.1f pips fill %.3f %s", side > 0 ? "BUY" : "SELL", lots, Pips(risk), g_trade.ResultPrice(), ok ? "" : g_trade.ResultRetcodeDescription()));
   return ok;
  }

bool PlaceBoxOrders()
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double box = g_boxHi - g_boxLo;
   double risk = box + (ask - bid);
   string why;
   if(!BoxPreflight(risk, why)) { Log("box not placed", why); return false; }
   double lots = LotsForRisk(InpRiskBox, risk);
   if(!GuardsAllow(lots, risk, why)) { Log("box blocked", why); return false; }
   datetime now = UtcNow(), placeUtc = g_boxDay + ParseHHMM(InpBoxPlaceUTC);
   bool late = (now > placeUtc + InpSignalWindowMin * 60);
   double stopsLvl = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * g_point;
   bool buyCrossed = (ask >= g_boxHi - stopsLvl), sellCrossed = (bid <= g_boxLo + stopsLvl);
   datetime when;
   if(late && LevelTouchedSince(placeUtc, true, true, when)) { Log("box not placed", "box already broken at " + Hm(when) + " UTC; the engine's trade 1 has happened"); g_boxDismissed = true; SaveState(); return false; }
   if(late && (buyCrossed || sellCrossed)) { Log("box not placed", "price is past the box and the 10-minute market window has passed"); g_boxDismissed = true; SaveState(); return false; }
   datetime expiry = ToServer(g_boxDay + ParseHHMM(InpBoxExpiryUTC));
   string cm = StringFormat("ABA-B1 b=%.4f r=%.4f", box, risk);
   g_boxRisk = risk;
   bool any = false;
   if(buyCrossed) any = MarketBox(1, lots, risk, cm);
   else if(sellCrossed) any = MarketBox(-1, lots, risk, cm);
   else
     {
      bool b = PlaceStop(true, lots, NormalizeDouble(g_boxHi, g_digits), NormalizeDouble(g_boxHi - risk, g_digits), NormalizeDouble(g_boxHi + InpBoxRR * risk, g_digits), expiry, cm);
      string bErr = b ? "" : g_trade.ResultRetcodeDescription();
      bool s = PlaceStop(false, lots, NormalizeDouble(g_boxLo, g_digits), NormalizeDouble(g_boxLo + risk, g_digits), NormalizeDouble(g_boxLo - InpBoxRR * risk, g_digits), expiry, cm);
      string sErr = s ? "" : g_trade.ResultRetcodeDescription();
      Log("box stops", StringFormat("buy stop %.3f %s %s, sell stop %.3f %s %s, lots %.2f, risk %.1f pips, expire %s UTC", g_boxHi, b ? "ok" : "FAILED", bErr, g_boxLo, s ? "ok" : "FAILED", sErr, lots, Pips(risk), Hm(g_boxDay + ParseHHMM(InpBoxExpiryUTC))));
      if(b != s)
        {
         // one side failed: if its level is crossed now, go to market on that side and drop the other; else drop everything and ask for a new click
         ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK); bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         if(!b && ask >= g_boxHi - stopsLvl) { DeleteBoxOrders(0, "buy side crossed"); any = MarketBox(1, lots, risk, cm); }
         else if(!s && bid <= g_boxLo + stopsLvl) { DeleteBoxOrders(0, "sell side crossed"); any = MarketBox(-1, lots, risk, cm); }
         else { DeleteBoxOrders(0, "one side failed, click again"); any = false; }
        }
      else any = b && s;
     }
   if(any) { g_boxPlaced = true; SaveState(); }
   return any;
  }

bool PlaceReentry()
  {
   if(g_reSide == 0 || g_reAt == 0) { Log("re-entry not placed", "no re-entry proposal"); return false; }
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double box = g_boxHi - g_boxLo;
   double risk = box + (ask - bid);
   string why;
   if(!BoxPreflight(risk, why)) { Log("re-entry not placed", why); return false; }
   double lots = LotsForRisk(InpRiskBox, risk);
   if(!GuardsAllow(lots, risk, why)) { Log("re-entry blocked", why); return false; }
   datetime when;
   if(LevelTouchedSince(g_reAt, g_reSide > 0, g_reSide < 0, when)) { Log("re-entry not placed", "level already touched at " + Hm(when) + " UTC since the re-entry time"); g_reentryPlaced = true; SaveState(); return false; }
   if(g_reSide > 0 && ask >= g_reLvl) { Log("re-entry skipped", "ask already above the box high"); g_reentryPlaced = true; SaveState(); return false; }
   if(g_reSide < 0 && bid <= g_reLvl) { Log("re-entry skipped", "bid already below the box low"); g_reentryPlaced = true; SaveState(); return false; }
   datetime expiry = ToServer(g_boxDay + ParseHHMM(InpBoxExpiryUTC));
   string cm = StringFormat("ABA-B2 b=%.4f r=%.4f", box, risk);
   bool ok = (g_reSide > 0) ? PlaceStop(true, lots, NormalizeDouble(g_reLvl, g_digits), NormalizeDouble(g_reLvl - risk, g_digits), NormalizeDouble(g_reLvl + InpBoxRR * risk, g_digits), expiry, cm)
                            : PlaceStop(false, lots, NormalizeDouble(g_reLvl, g_digits), NormalizeDouble(g_reLvl + risk, g_digits), NormalizeDouble(g_reLvl - InpBoxRR * risk, g_digits), expiry, cm);
   if(ok) { g_boxRisk = risk; g_reentryPlaced = true; g_reTicket = g_trade.ResultOrder(); SaveState(); Log("re-entry stop placed", StringFormat("%s stop #%s at %.3f lots %.2f risk %.1f pips", g_reSide > 0 ? "buy" : "sell", Tk(g_reTicket), g_reLvl, lots, Pips(risk))); }
   else Log("re-entry FAILED", g_trade.ResultRetcodeDescription());
   return ok;
  }

bool PlaceGotobi()
  {
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double dist = InpGotobiSlAtr * g_atr20;
   if(dist <= 0 || (InpVolFilter && !g_volOn)) { Log("gotobi not placed", "no ATR or vol filter OFF"); return false; }
   double lots = LotsForRisk(InpRiskGotobi, dist);
   string why;
   if(!GuardsAllow(lots, dist, why)) { Log("gotobi blocked", why); return false; }
   bool ok = g_trade.Sell(lots, _Symbol, 0, NormalizeDouble(bid + dist, g_digits), 0, "ABA-G");
   if(ok) { g_gotobiRisk = dist; g_gotobiTaken = true; SaveState(); Log("gotobi SELL", StringFormat("lots %.2f, stop %.1f pips, bid at click %.3f, fill %.3f", lots, Pips(dist), bid, g_trade.ResultPrice())); }
   else Log("gotobi FAILED", g_trade.ResultRetcodeDescription());
   return ok;
  }

bool PlaceM3()
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double dist = InpM3SlAtr * g_atr20;
   if(dist <= 0) { Log("M-3 not placed", "no ATR"); return false; }
   double lots = LotsForRisk(InpRiskM3, dist);
   string why;
   if(!GuardsAllow(lots, dist, why)) { Log("M-3 blocked", why); return false; }
   bool ok = g_trade.Buy(lots, _Symbol, 0, NormalizeDouble(ask - dist, g_digits), 0, "ABA-M");
   if(ok) { g_m3Risk = dist; g_m3Taken = true; SaveState(); Log("M-3 BUY", StringFormat("lots %.2f, stop %.1f pips, ask at click %.3f, fill %.3f", lots, Pips(dist), ask, g_trade.ResultPrice())); }
   else Log("M-3 FAILED", g_trade.ResultRetcodeDescription());
   return ok;
  }

//+------------------------------------------------------------------+
//| management (automatic)                                            |
//+------------------------------------------------------------------+
// stop orders left from a pair whose other side has filled (independent of the order comments)
void CleanupSiblings()
  {
   if(g_bt.trades >= 2) { if(CountBoxOrders() > 0) DeleteBoxOrders(0, "two trades done"); return; }
   if(g_bt.trades >= 1)
     {
      ulong keep = (g_reentryPlaced && g_reTicket != 0 && IsBoxOrder(g_reTicket)) ? g_reTicket : 0;
      if(CountBoxOrders() > (keep != 0 ? 1 : 0)) DeleteBoxOrders(keep, "OCO sibling");
     }
  }

// after a fill of a box order: SL/TP from the fill price with the order's own risk (never loosening a stop)
void AdjustBoxFill(const ulong ticket)
  {
   if(!PositionSelectByTicket(ticket)) return;
   double op = PositionGetDouble(POSITION_PRICE_OPEN), sl = PositionGetDouble(POSITION_SL), tp = PositionGetDouble(POSITION_TP);
   long type = PositionGetInteger(POSITION_TYPE);
   int side = (type == POSITION_TYPE_BUY) ? 1 : -1;
   double risk = FromComment(PositionGetString(POSITION_COMMENT), "r=", g_boxRisk);
   if(risk <= 0) return;
   double wantSl = op - side * risk;
   double wantTp = op + side * InpBoxRR * risk;
   bool slTighter = (sl > 0) && ((side > 0) ? (sl >= wantSl - g_point) : (sl <= wantSl + g_point));
   bool tpOk = MathAbs(tp - wantTp) <= g_point;
   if(!tpOk || sl <= 0)
     {
      double newSl = slTighter ? sl : wantSl;
      if(g_trade.PositionModify(ticket, NormalizeDouble(newSl, g_digits), NormalizeDouble(wantTp, g_digits)))
         Log("box fill adjusted", StringFormat("%s at %.3f: SL %.3f TP %.3f", side > 0 ? "BUY" : "SELL", op, newSl, wantTp));
      else LogFail("box fill adjust FAILED", g_trade.ResultRetcodeDescription());
     }
  }

// break-even for every box position (today's or older)
void ManageBoxPositions()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || !PositionSelectByTicket(t) || !IsOurs(InpMagicBox)) continue;
      double op = PositionGetDouble(POSITION_PRICE_OPEN), sl = PositionGetDouble(POSITION_SL), tp = PositionGetDouble(POSITION_TP);
      long type = PositionGetInteger(POSITION_TYPE);
      int side = (type == POSITION_TYPE_BUY) ? 1 : -1;
      string cm = PositionGetString(POSITION_COMMENT);
      double risk = FromComment(cm, "r=", (tp > 0) ? MathAbs(tp - op) / InpBoxRR : ((sl > 0) ? MathAbs(op - sl) : 0));
      if(risk <= 0) continue;
      double box = FromComment(cm, "b=", risk);
      double beStop = op + side * box / InpBoxBeOffsetDiv;
      double trig = op + side * InpBoxBeTriggerR * risk;
      double px = (side > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      bool reached = (side > 0) ? (px >= trig) : (px <= trig);
      bool notYet = (sl <= 0) || ((side > 0) ? (sl < beStop - g_point / 2) : (sl > beStop + g_point / 2));
      if(reached && notYet)
        {
         if(g_trade.PositionModify(t, NormalizeDouble(beStop, g_digits), tp)) Log("break-even", StringFormat("#%s +%.0fR reached, stop moved to %.3f", Tk(t), InpBoxBeTriggerR, beStop));
         else LogFail("break-even FAILED", "#" + Tk(t) + " " + g_trade.ResultRetcodeDescription());
        }
     }
  }

// gotobi / M-3: make sure the stop exists and is not looser than intended; never move a stop the user tightened; keep the TP
void EnsureStop(const long magic, const double dist, const string tag)
  {
   ulong t = FirstPosition(magic);
   if(t == 0 || !PositionSelectByTicket(t) || dist <= 0) return;
   double op = PositionGetDouble(POSITION_PRICE_OPEN), sl = PositionGetDouble(POSITION_SL), tp = PositionGetDouble(POSITION_TP);
   long type = PositionGetInteger(POSITION_TYPE);
   double want = (type == POSITION_TYPE_BUY) ? op - dist : op + dist;
   bool looser = (sl <= 0) || ((type == POSITION_TYPE_BUY) ? (sl < want - g_point) : (sl > want + g_point));
   if(looser)
     {
      if(g_trade.PositionModify(t, NormalizeDouble(want, g_digits), tp)) Log(tag + " stop set", StringFormat("entry %.3f stop %.3f", op, want));
      else LogFail(tag + " stop set FAILED", g_trade.ResultRetcodeDescription());
     }
  }

//+------------------------------------------------------------------+
//| main update                                                       |
//+------------------------------------------------------------------+
void Update()
  {
   UpdateOffset();
   datetime now = UtcNow();
   g_todayUtc = DateOf(now);
   int sec = SecOfDay(now);
   UpdateAtr();
   UpdateDayStart();
   g_actBox = ACT_NONE; g_actTimed = ACT_NONE; g_actBoxUntil = 0; g_actTimedUntil = 0;
   g_reSide = 0; g_reLvl = 0; g_reAt = 0;

   //--- box: management of any box position/order, then today's state machine
   ManageBoxPositions();
   DeleteStaleBoxOrders();
   int placeSec = ParseHHMM(InpBoxPlaceUTC), expSec = ParseHHMM(InpBoxExpiryUTC);
   if(sec >= placeSec && g_boxDay != g_todayUtc) StartBoxDay(g_todayUtc);
   BoxTodayStats(g_bt);
   if(g_boxDay == g_todayUtc)
     {
      datetime expiry = g_boxDay + expSec;
      CleanupSiblings();
      if(g_bt.openPos != 0) AdjustBoxFill(g_bt.openPos);
      if(!g_boxPlaced && (g_bt.trades > 0 || CountBoxOrdersToday() > 0)) { g_boxPlaced = true; SaveState(); }   // today's orders or fills exist: placed
      if(g_boxSkipCode == SKIP_NONE && !g_boxDismissed)
        {
         bool orders = CountBoxOrders() > 0;
         if(!g_boxPlaced)
           {
            if(now >= expiry) g_boxNote = "expired, never placed";
            else
              {
               datetime placeUtc = g_boxDay + placeSec, when;
               bool late = (now > placeUtc + InpSignalWindowMin * 60);
               double stopsLvl = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * g_point;
               bool crossed = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) >= g_boxHi - stopsLvl) || (SymbolInfoDouble(_Symbol, SYMBOL_BID) <= g_boxLo + stopsLvl);
               if(late && LevelTouchedSince(placeUtc, true, true, when))
                 { g_boxDismissed = true; g_boxNote = "box broken at " + Hm(when) + " UTC before placement: no box trade today"; Log("box closed for today", g_boxNote); SaveState(); }
               else if(late && crossed)
                 { g_boxDismissed = true; g_boxNote = "price past the box after the placement window: no box trade today"; Log("box closed for today", g_boxNote); SaveState(); }
               else { g_actBox = ACT_BOX; g_actBoxUntil = expiry; g_boxNote = "ready"; }
              }
           }
         else if(g_bt.openPos != 0) g_boxNote = StringFormat("trade %d open", g_bt.trades);
         else if(orders) g_boxNote = "stop order(s) working";
         else if(g_bt.trades == 0) g_boxNote = (now < expiry) ? "orders gone, none filled" : "orders expired unfilled";
         else if(g_bt.trades >= 2) g_boxNote = "done: two trades";
         else if(g_bt.lastClosed && g_bt.lastReason == DEAL_REASON_TP) g_boxNote = "done: take profit";
         else if(g_bt.lastClosed && g_bt.lastReason != DEAL_REASON_SL) g_boxNote = "done: closed manually";
         else if(g_bt.lastClosed && g_bt.lastCloseUtc >= expiry) g_boxNote = "done: stopped after expiry";
         else if(g_bt.lastClosed)
           {
            datetime reAt = g_bt.lastCloseUtc + InpReentryWaitMin * 60;
            int reSide = (g_bt.lastSide > 0) ? -1 : 1;
            double reLvl = (g_bt.lastSide > 0) ? g_boxLo : g_boxHi;
            datetime when;
            if(g_reentryPlaced) g_boxNote = "done: re-entry used or declined";
            else if(reAt >= expiry) g_boxNote = "done: re-entry window past expiry";
            else if(now < reAt) g_boxNote = StringFormat("stopped at %s; re-entry %s stop at %.3f from %s UTC", Hm(g_bt.lastCloseUtc), reSide > 0 ? "buy" : "sell", reLvl, Hm(reAt));
            else if(LevelTouchedSince(reAt, reSide > 0, reSide < 0, when))
              { g_reentryPlaced = true; g_boxNote = "done: re-entry level touched at " + Hm(when) + " UTC before it was placed"; Log("re-entry closed", g_boxNote); SaveState(); }
            else { g_reSide = reSide; g_reLvl = reLvl; g_reAt = reAt; g_actBox = ACT_REENTRY; g_actBoxUntil = expiry; g_boxNote = StringFormat("RE-ENTRY READY: %s stop at %.3f", reSide > 0 ? "buy" : "sell", reLvl); }
           }
        }
     }

   //--- gotobi
   int gEntry = ParseHHMM(InpGotobiEntryUTC), gExit = ParseHHMM(InpGotobiExitUTC);
   bool gotobiToday = IsWeekday(g_todayUtc) && IsGotobiDate(g_todayUtc);
   if(g_gotobiDay != g_todayUtc) { g_gotobiDay = g_todayUtc; g_gotobiTaken = false; g_gotobiDismissed = false; g_gotobiRisk = 0; SaveState(); }
   if(InpGotobiOn && gotobiToday && g_volOn && !g_gotobiTaken && !g_gotobiDismissed && sec >= gEntry && sec < gEntry + InpSignalWindowMin * 60)
     { g_actTimed = ACT_GOTOBI; g_actTimedUntil = g_todayUtc + gEntry + InpSignalWindowMin * 60; }
   if(g_gotobiTaken && g_gotobiRisk > 0) EnsureStop(InpMagicGotobi, g_gotobiRisk, "gotobi");
   ClosePositionsByTime(InpMagicGotobi, gExit, "gotobi");

   //--- M-3
   int mEntry = ParseHHMM(InpM3EntryUTC), mExit = ParseHHMM(InpM3ExitUTC);
   bool m3Today = IsM3Date(g_todayUtc);
   if(g_m3Day != g_todayUtc) { g_m3Day = g_todayUtc; g_m3Taken = false; g_m3Dismissed = false; g_m3Risk = 0; SaveState(); }
   if(InpM3On && m3Today && !g_m3Taken && !g_m3Dismissed && sec >= mEntry && sec < mEntry + InpSignalWindowMin * 60 && g_actTimed == ACT_NONE)
     { g_actTimed = ACT_M3; g_actTimedUntil = g_todayUtc + mEntry + InpSignalWindowMin * 60; }
   if(g_m3Taken && g_m3Risk > 0) EnsureStop(InpMagicM3, g_m3Risk, "M-3");
   ClosePositionsByTime(InpMagicM3, mExit, "M-3");

   DrawPanel(now, sec, gotobiToday, m3Today);
  }

//+------------------------------------------------------------------+
//| dashboard                                                         |
//+------------------------------------------------------------------+
string ButtonLabel(const ACTION a, color &bgc)
  {
   bgc = C_IDLE;
   if(a == ACT_NONE) return "no signal";
   double lots = 0, dist = 0;
   string why = "";
   if(a == ACT_BOX || a == ACT_REENTRY) { dist = g_boxHi - g_boxLo + Spread(); if(!BoxPreflight(dist, why)) { bgc = C_BAD; return "BLOCKED: " + why; } lots = LotsForRisk(InpRiskBox, dist); }
   if(a == ACT_GOTOBI) { dist = InpGotobiSlAtr * g_atr20; lots = LotsForRisk(InpRiskGotobi, dist); }
   if(a == ACT_M3) { dist = InpM3SlAtr * g_atr20; lots = LotsForRisk(InpRiskM3, dist); }
   bool allowed = GuardsAllow(lots, dist, why);
   string what = (a == ACT_BOX) ? "PLACE BOX STOP ORDERS" : (a == ACT_REENTRY) ? "PLACE RE-ENTRY STOP" : (a == ACT_GOTOBI) ? "SELL GOTOBI NOW" : "BUY M-3 NOW";
   datetime until = (a == ACT_BOX || a == ACT_REENTRY) ? g_actBoxUntil : g_actTimedUntil;
   bgc = allowed ? C_OK : C_BAD;
   // chart object text is limited to 63 characters
   return Fit(allowed ? StringFormat("%s  %.2f lots  $%.0f risk  until %s", what, lots, LossAtStop(lots, dist), Hm(until)) : ("BLOCKED: " + why), 63);
  }

// one leg card: pill + three short lines + a note
void LegCard(const string id, const int x, const int y, const string title, const string pill, const color pillClr,
             const string l1, const string l2, const string l3, const string note, const color noteClr)
  {
   Card(id, x, y, CARD_W, 124, title);
   Pill(id + "_s", x + CARD_W - 118, y + 1, 110, pill, pillClr);
   Text(PFX + id + "_1", x + 8, y + 26, Fit(l1, 44), C_TXT, InpFontSize, FontText());
   Text(PFX + id + "_2", x + 8, y + 44, Fit(l2, 44), C_TXT, InpFontSize, FontText());
   Text(PFX + id + "_3", x + 8, y + 62, Fit(l3, 44), C_TXT, InpFontSize, FontText());
   Text(PFX + id + "_n", x + 8, y + 86, Fit(note, 46), noteClr, InpFontSize, FontText());
  }

void DrawPanel(const datetime now, const int sec, const bool gotobiToday, const bool m3Today)
  {
   bool autoOk = TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) && MQLInfoInteger(MQL_TRADE_ALLOWED);
   int x0 = InpPanelX + GAP;
   // ---- title bar
   int y = LayY(0);
   Rect(PFX + "TB", InpPanelX, y, PANEL_W, 26, C_HEAD, C_HEAD);
   Text(PFX + "T1", x0, y + 4, "ALPHA BASKET ASSISTANT  v1.04", C_TXT, InpFontSize + 1, FontHead());
   Text(PFX + "T2", x0 + 250, y + 5, Fit(StringFormat("%s     %s UTC     server %+.0f h", _Symbol, TimeToString(now, TIME_DATE | TIME_SECONDS), g_offSec / 3600.0), 63), C_DIM, InpFontSize, FontText());
   string health = (!autoOk) ? "AUTOTRADING OFF" : (!g_offOk) ? "CHECK TIME ZONE" : (!g_clockOk) ? "CHECK PC CLOCK" : "ALL SYSTEMS OK";
   color healthClr = (autoOk && g_offOk && g_clockOk) ? C_OK : C_BAD;
   Pill("HP", InpPanelX + PANEL_W - 150, y + 4, 142, health, healthClr);

   // ---- row 1: account, safety, vol filter
   y = LayY(1);
   int cx1 = x0, cx2 = x0 + CARD_W + GAP, cx3 = x0 + 2 * (CARD_W + GAP);
   // account
   Card("AC", cx1, y, CARD_W, 104, "ACCOUNT");
   double prog = InpAccountStart > 0 ? 100.0 * (Balance() - InpAccountStart) / InpAccountStart : 0;
   KV("AC1", cx1 + 8, y + 26, 92, "Balance", StringFormat("%.2f", Balance()));
   KV("AC2", cx1 + 8, y + 44, 92, "Equity", StringFormat("%.2f", Equity()));
   KV("AC3", cx1 + 8, y + 62, 92, "Target", StringFormat("%+.2f%% of +%.1f%%", prog, InpTargetPct), prog >= InpTargetPct ? C_OK : C_TXT);
   Bar("ACB", cx1 + 8, y + 86, CARD_W - 16, (InpTargetPct > 0) ? prog / InpTargetPct : 0, C_OK);
   // safety
   Card("SF", cx2, y, CARD_W, 104, "TODAY'S SAFETY");
   double du = MathMax(DailyUsedPct(), 0), mu = MathMax(MaxUsedPct(), 0);
   bool unb; double wEq = WorstCaseEquity(0, 0, unb);
   double dWorst = (g_dayStart > 0) ? 100.0 * (g_dayStart - wEq) / g_dayStart : 0;
   KV("SF1", cx2 + 8, y + 24, 118, "Daily loss used", StringFormat("%.2f%% of %.1f%%", du, InpDailyGuardPct), du >= InpDailyGuardPct ? C_BAD : (du > InpDailyGuardPct / 2 ? C_WARN : C_TXT));
   Bar("SFB1", cx2 + 8, y + 40, CARD_W - 16, du / InpDailyGuardPct, du >= InpDailyGuardPct ? C_BAD : C_WARN);
   KV("SF2", cx2 + 8, y + 50, 118, "Max loss used", StringFormat("%.2f%% of %.1f%%", mu, InpMaxGuardPct), mu >= InpMaxGuardPct ? C_BAD : C_TXT);
   Bar("SFB2", cx2 + 8, y + 66, CARD_W - 16, mu / InpMaxGuardPct, mu >= InpMaxGuardPct ? C_BAD : C_WARN);
   KV("SF3", cx2 + 8, y + 76, 118, "If all stops hit", unb ? "a trade has NO STOP" : StringFormat("%.2f%% today (budget %.1f%%)", dWorst, InpBudgetPct), unb ? C_BAD : (dWorst > InpBudgetPct ? C_WARN : C_TXT));
   Text(PFX + "SF4", cx2 + 8, y + 90, ProtectActive() ? "Protect ON: every risk halved" : StringFormat("Risk %.2g / %.2g / %.2g %%   lot cap %.0f", InpRiskBox, InpRiskGotobi, InpRiskM3, InpMaxLots), ProtectActive() ? C_WARN : C_DIM, InpFontSize - 1, FontText());
   // vol filter
   Card("VF", cx3, y, CARD_W, 104, "VOL FILTER (box + gotobi)");
   bool shortHist = (g_histBars < InpAtrDays + InpMedianDays - 1);
   Pill("VF_s", cx3 + 8, y + 28, 70, g_volOn ? "ON" : "OFF", g_volOn ? C_OK : C_WARN);
   Text(PFX + "VF1", cx3 + 88, y + 28, g_volOn ? "box and gotobi trade today" : (shortHist ? "history still loading" : "both legs skipped today"), g_volOn ? C_TXT : C_WARN, InpFontSize, FontText());
   KV("VF2", cx3 + 8, y + 56, 110, "ATR20", StringFormat("%.1f pips", Pips(g_atr20)));
   KV("VF3", cx3 + 8, y + 74, 110, StringFormat("Median %d", InpMedianDays), StringFormat("%.1f pips", Pips(g_median)));
   Text(PFX + "VF4", cx3 + 8, y + 90, shortHist ? StringFormat("%d of %d daily bars loaded", g_histBars, InpAtrDays + InpMedianDays - 1) : "ON when ATR20 >= median", C_DIM, InpFontSize - 1, FontText());

   // ---- row 2: legs
   y = LayY(2);
   // box
   string bPill = "WAITING"; color bClr = C_IDLE; string bNote = ""; color bNoteClr = C_DIM;
   string b1, b2, b3;
   int expSec = ParseHHMM(InpBoxExpiryUTC);
   bool boxOpen = (g_bt.openPos != 0), boxOrders = (CountBoxOrders() > 0);
   if(g_boxDay != g_todayUtc)
     {
      bPill = "WAITING"; bClr = C_IDLE;
      b1 = StringFormat("Box forms %s-%s UTC", InpBoxStartUTC, Hm(g_todayUtc + ParseHHMM(InpBoxStartUTC) + (InpBoxMinutes - 1) * 60));
      b2 = StringFormat("Orders at %s UTC, expire %s UTC", InpBoxPlaceUTC, InpBoxExpiryUTC);
      b3 = StringFormat("Risk %.2g%%   RR %.0f   BE at +%.0fR", InpRiskBox, InpBoxRR, InpBoxBeTriggerR);
      bNote = (sec >= ParseHHMM(InpBoxPlaceUTC) && g_boxNote != "") ? g_boxNote : "nothing to do yet";
     }
   else
     {
      double risk = g_boxHi - g_boxLo + Spread();
      b1 = StringFormat("Box %.3f - %.3f   %.1f pips", g_boxLo, g_boxHi, Pips(g_boxHi - g_boxLo));
      b2 = StringFormat("Stop %.1f   TP %.0f pips   %.2f lots", Pips(risk), Pips(InpBoxRR * risk), LotsForRisk(InpRiskBox, risk));
      b3 = StringFormat("Trades today %d of 2   %d bars", g_bt.trades, g_boxBars);
      if(g_boxSkipCode != SKIP_NONE) { bPill = "SKIPPED"; bClr = C_WARN; bNote = SkipText(g_boxSkipCode); bNoteClr = C_WARN; }
      else if(g_boxDismissed) { bPill = "SKIPPED"; bClr = C_WARN; bNote = (g_boxNote == "" || g_boxNote == "ready") ? "skipped by you" : g_boxNote; bNoteClr = C_WARN; }
      else if(g_actBox == ACT_BOX) { bPill = "READY"; bClr = C_OK; bNote = "click PLACE BOX STOP ORDERS below"; bNoteClr = C_OK; }
      else if(g_actBox == ACT_REENTRY) { bPill = "RE-ENTRY"; bClr = C_OK; bNote = g_boxNote; bNoteClr = C_OK; }
      else if(boxOpen) { bPill = "IN TRADE"; bClr = C_INFO; bNote = g_boxNote; bNoteClr = C_TXT; }
      else if(boxOrders) { bPill = "WORKING"; bClr = C_INFO; bNote = StringFormat("stop orders working until %s UTC", InpBoxExpiryUTC); bNoteClr = C_TXT; }
      else if(!g_boxPlaced && now >= g_boxDay + expSec) { bPill = "DONE"; bClr = C_IDLE; bNote = "expired, never placed"; }
      else { bPill = "DONE"; bClr = C_IDLE; bNote = g_boxNote; }
     }
   LegCard("LB", cx1, y, "BOX BREAKOUT  06:00 IST", bPill, bClr, b1, b2, b3, bNote, bNoteClr);
   // gotobi
   string gPill, g1, g2, g3, gNote = ""; color gClr, gNoteClr = C_DIM;
   datetime ng = NextDate(g_todayUtc + (gotobiToday ? 86400 : 0), true);
   double gDist = InpGotobiSlAtr * g_atr20;
   g2 = StringFormat("Sell %s UTC, close %s UTC", InpGotobiEntryUTC, InpGotobiExitUTC);
   g3 = StringFormat("Stop %.1f pips   %.2f lots   risk %.2g%%", Pips(gDist), LotsForRisk(InpRiskGotobi, gDist), InpRiskGotobi);
   if(!InpGotobiOn) { gPill = "OFF"; gClr = C_IDLE; g1 = "leg disabled in inputs"; }
   else if(!gotobiToday) { gPill = "NOT TODAY"; gClr = C_IDLE; g1 = "Next: " + TimeToString(ng, TIME_DATE); gNote = "5/10/15/20/25/month-end, weekend -> Friday"; }
   else if(!g_volOn) { gPill = "VOL OFF"; gClr = C_WARN; g1 = "Gotobi day, but vol filter OFF"; gNote = "skipped today, that is the rule"; gNoteClr = C_WARN; }
   else if(g_gotobiTaken) { gPill = (FirstPosition(InpMagicGotobi) != 0) ? "OPEN" : "DONE"; gClr = (FirstPosition(InpMagicGotobi) != 0) ? C_INFO : C_IDLE; g1 = "Gotobi day: trade taken"; gNote = (FirstPosition(InpMagicGotobi) != 0) ? ("closes itself at " + InpGotobiExitUTC + " UTC") : "closed"; }
   else if(g_gotobiDismissed) { gPill = "SKIPPED"; gClr = C_WARN; g1 = "Gotobi day"; gNote = "skipped by you"; gNoteClr = C_WARN; }
   else if(sec < ParseHHMM(InpGotobiEntryUTC)) { gPill = "TODAY"; gClr = C_INFO; g1 = "Gotobi day: sell at " + InpGotobiEntryUTC + " UTC"; gNote = "be at the screen at 06:25 IST"; gNoteClr = C_TXT; }
   else if(g_actTimed == ACT_GOTOBI) { gPill = "SIGNAL"; gClr = C_OK; g1 = "Gotobi day: SELL now"; gNote = "click SELL GOTOBI NOW below"; gNoteClr = C_OK; }
   else { gPill = "MISSED"; gClr = C_WARN; g1 = "Gotobi day"; gNote = "the 10-minute window passed"; gNoteClr = C_WARN; }
   LegCard("LG", cx2, y, "GOTOBI SHORT  06:25 IST", gPill, gClr, g1, g2, g3, gNote, gNoteClr);
   // m3
   string mPill, m1, m2, m3, mNote = ""; color mClr, mNoteClr = C_DIM;
   datetime nm = NextDate(g_todayUtc + (m3Today ? 86400 : 0), false);
   double mDist = InpM3SlAtr * g_atr20;
   m2 = StringFormat("Buy %s UTC, close %s UTC", InpM3EntryUTC, InpM3ExitUTC);
   m3 = StringFormat("Stop %.1f pips   %.2f lots   risk %.2g%%", Pips(mDist), LotsForRisk(InpRiskM3, mDist), InpRiskM3);
   if(!InpM3On) { mPill = "OFF"; mClr = C_IDLE; m1 = "leg disabled in inputs"; }
   else if(!m3Today) { mPill = "NOT TODAY"; mClr = C_IDLE; m1 = "Next: " + TimeToString(nm, TIME_DATE); mNote = "3rd-last weekday of the month"; }
   else if(g_m3Taken) { mPill = (FirstPosition(InpMagicM3) != 0) ? "OPEN" : "DONE"; mClr = (FirstPosition(InpMagicM3) != 0) ? C_INFO : C_IDLE; m1 = "Month-end day: trade taken"; mNote = (FirstPosition(InpMagicM3) != 0) ? ("closes itself at " + InpM3ExitUTC + " UTC") : "closed"; }
   else if(g_m3Dismissed) { mPill = "SKIPPED"; mClr = C_WARN; m1 = "Month-end day"; mNote = "skipped by you"; mNoteClr = C_WARN; }
   else if(sec < ParseHHMM(InpM3EntryUTC)) { mPill = "TODAY"; mClr = C_INFO; m1 = "Month-end day: buy at " + InpM3EntryUTC + " UTC"; mNote = "be at the screen at 16:30 IST"; mNoteClr = C_TXT; }
   else if(g_actTimed == ACT_M3) { mPill = "SIGNAL"; mClr = C_OK; m1 = "Month-end day: BUY now"; mNote = "click BUY M-3 NOW below"; mNoteClr = C_OK; }
   else { mPill = "MISSED"; mClr = C_WARN; m1 = "Month-end day"; mNote = "the 10-minute window passed"; mNoteClr = C_WARN; }
   LegCard("LM", cx3, y, "MONTH-END BID  16:30 IST", mPill, mClr, m1, m2, m3, mNote, mNoteClr);

   // ---- row 3: open positions
   y = LayY(3);
   int pw = 3 * CARD_W + 2 * GAP;
   Card("PO", x0, y, pw, 92, "OPEN BASKET POSITIONS");
   Text(PFX + "PO_h", x0 + 8, y + 24, "LEG     SIDE  LOTS    ENTRY     STOP       R       P/L   SINCE", C_DIM, InpFontSize, FontMono());
   int shown = 0, others = 0;
   for(int i = 0; i < PositionsTotal(); i++)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || !PositionSelectByTicket(t)) continue;
      long magic = PositionGetInteger(POSITION_MAGIC);
      string name = (magic == InpMagicBox) ? "box" : (magic == InpMagicGotobi) ? "gotobi" : (magic == InpMagicM3) ? "M-3" : "";
      if(name == "" || PositionGetString(POSITION_SYMBOL) != _Symbol) { others++; continue; }
      if(shown < 3)
        {
         long type = PositionGetInteger(POSITION_TYPE);
         double op = PositionGetDouble(POSITION_PRICE_OPEN), sl = PositionGetDouble(POSITION_SL), tp = PositionGetDouble(POSITION_TP), vol = PositionGetDouble(POSITION_VOLUME);
         double px = (type == POSITION_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double move = (type == POSITION_TYPE_BUY) ? px - op : op - px;
         double risk = (magic == InpMagicBox) ? FromComment(PositionGetString(POSITION_COMMENT), "r=", (tp > 0) ? MathAbs(tp - op) / InpBoxRR : 0) : (magic == InpMagicGotobi ? g_gotobiRisk : g_m3Risk);
         string r = (risk > 0) ? StringFormat("%+.2fR", move / risk) : "  -   ";
         double pl = PositionGetDouble(POSITION_PROFIT);
         Text(PFX + "PO_" + IntegerToString(shown), x0 + 8, y + 40 + 16 * shown,
              Fit(StringFormat("%-7s %-5s %5.2f  %8.3f  %8.3f  %7s  %+8.2f  %s", name, type == POSITION_TYPE_BUY ? "BUY" : "SELL", vol, op, sl, r, pl, TimeToString((datetime)PositionGetInteger(POSITION_TIME), TIME_MINUTES)), 63),
              pl >= 0 ? C_TXT : C_WARN, InpFontSize, FontMono());
        }
      shown++;
     }
   for(int i = shown; i < 3; i++) Text(PFX + "PO_" + IntegerToString(i), x0 + 8, y + 40 + 16 * i, i == 0 ? "(none)" : " ", C_DIM, InpFontSize, FontMono());
   Text(PFX + "PO_f", x0 + pw - 330, y + 2, StringFormat("other positions %d   box orders working %d%s", others, CountBoxOrders(), shown > 3 ? StringFormat("   +%d more", shown - 3) : ""), C_DIM, InpFontSize - 1, FontText());

   // ---- row 4: buttons
   color c1, c2;
   string l1 = ButtonLabel(g_actBox, c1), l2 = ButtonLabel(g_actTimed, c2);
   Button(BTN_BOX, x0, ButtonsY(), 600, 30, g_actBox == ACT_NONE ? "BOX: no signal" : l1, c1);
   Button(BTN_BOX_SKIP, x0 + 612, ButtonsY(), 252, 30, g_actBox == ACT_NONE ? "-" : (g_actBox == ACT_BOX ? "skip box today" : "skip re-entry"), g_actBox == ACT_NONE ? C_IDLE : C_HEAD);
   Button(BTN_TM, x0, ButtonsY() + 38, 600, 30, g_actTimed == ACT_NONE ? "GOTOBI / M-3: no signal" : l2, c2);
   Button(BTN_TM_SKIP, x0 + 612, ButtonsY() + 38, 252, 30, g_actTimed == ACT_NONE ? "-" : "skip this signal", g_actTimed == ACT_NONE ? C_IDLE : C_HEAD);
   g_drawnBox = g_actBox; g_drawnTimed = g_actTimed;

   // ---- footer
   y = LayY(5);
   Text(PFX + "FT", x0, y + 2, Fit("last: " + g_msg, 63), C_DIM, InpFontSize - 1, FontText());
   ChartRedraw();
  }

//+------------------------------------------------------------------+
//| events                                                            |
//+------------------------------------------------------------------+
int OnInit()
  {
   g_digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   g_point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   g_pip = (g_digits == 3 || g_digits == 5) ? 10 * g_point : g_point;
   g_key = PFX + IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN)) + "_" + _Symbol + "_";
   if(ParseHHMM(InpBoxStartUTC) < 0 || ParseHHMM(InpBoxPlaceUTC) < 0 || ParseHHMM(InpBoxExpiryUTC) < 0 ||
      ParseHHMM(InpGotobiEntryUTC) < 0 || ParseHHMM(InpGotobiExitUTC) < 0 || ParseHHMM(InpM3EntryUTC) < 0 || ParseHHMM(InpM3ExitUTC) < 0)
     { Print("bad HH:MM input"); return INIT_PARAMETERS_INCORRECT; }
   if(InpBoxRR <= InpBoxBeTriggerR || InpBoxBeOffsetDiv <= 0 || InpAtrDays <= 0 || InpMedianDays <= 0 || InpBoxMinutes <= 0 || InpMaxLots <= 0)
     { Print("bad numeric input (RR must exceed the BE trigger; windows, divisor and lot cap > 0)"); return INIT_PARAMETERS_INCORRECT; }
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     { Print("this account is not a hedging account: the legs would merge into one position"); return INIT_FAILED; }
   if(StringFind(_Symbol, "USDJPY") != 0) Print("warning: the basket was tested on USDJPY; the chart symbol is ", _Symbol);
   long expMode = SymbolInfoInteger(_Symbol, SYMBOL_EXPIRATION_MODE);
   if((expMode & SYMBOL_EXPIRATION_SPECIFIED) == 0) Print("warning: the symbol does not support ORDER_TIME_SPECIFIED; stop orders will be GTC and deleted by the EA at expiry");
   g_trade.SetExpertMagicNumber(InpMagicBox);
   g_trade.SetDeviationInPoints(InpDeviationPts);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_trade.SetAsyncMode(false);
   LoadState();
   CreatePanel();
   EventSetTimer(1);
   Log("init", StringFormat("v1.04 %s digits %d pip %.5f; login %s; account start %.0f target %.1f%%; risk %.2g/%.2g/%.2g%%; expiration mode %d", _Symbol, g_digits, g_pip, IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN)), InpAccountStart, InpTargetPct, InpRiskBox, InpRiskGotobi, InpRiskM3, (int)expMode));
   Update();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   SaveState();
   ObjectsDeleteAll(0, PFX);
  }

void OnTick() { Update(); }
void OnTimer() { Update(); }

void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;
   long magic = HistoryDealGetInteger(trans.deal, DEAL_MAGIC);
   long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   double price = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   long reason = HistoryDealGetInteger(trans.deal, DEAL_REASON);
   string leg = (magic == InpMagicBox) ? "box" : (magic == InpMagicGotobi) ? "gotobi" : (magic == InpMagicM3) ? "M-3" : "";
   if(leg == "") return;
   if(entry == DEAL_ENTRY_IN)
     {
      if(magic == InpMagicBox)
        {
         double lvl = (price >= g_boxHi) ? g_boxHi : ((price <= g_boxLo) ? g_boxLo : price);
         Log("fill", StringFormat("box %s at %.3f (level %.3f, slip %.1f pips)", HistoryDealGetInteger(trans.deal, DEAL_TYPE) == DEAL_TYPE_BUY ? "BUY" : "SELL", price, lvl, Pips(MathAbs(price - lvl))));
         BoxTodayStats(g_bt);
         CleanupSiblings();
         ulong t = PositionByIdentifier(HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID));
         if(t != 0) AdjustBoxFill(t);
        }
      else Log("fill", StringFormat("%s at %.3f", leg, price));
     }
   else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
      Log("exit", StringFormat("%s at %.3f reason %s profit %+.2f", leg, price, reason == DEAL_REASON_SL ? "SL" : reason == DEAL_REASON_TP ? "TP" : reason == DEAL_REASON_EXPERT ? "EA" : "other", HistoryDealGetDouble(trans.deal, DEAL_PROFIT)));
  }

void SetMagicFor(const ACTION a)
  {
   if(a == ACT_GOTOBI) g_trade.SetExpertMagicNumber(InpMagicGotobi);
   else if(a == ACT_M3) g_trade.SetExpertMagicNumber(InpMagicM3);
   else g_trade.SetExpertMagicNumber(InpMagicBox);
  }

void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(id != CHARTEVENT_OBJECT_CLICK) return;
   if(sparam != BTN_BOX && sparam != BTN_BOX_SKIP && sparam != BTN_TM && sparam != BTN_TM_SKIP) return;
   ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
   ACTION shownBox = g_drawnBox, shownTimed = g_drawnTimed;
   Update();                                   // recompute; act only if the signal is still the one the button showed
   if(sparam == BTN_BOX)
     {
      if(g_actBox == ACT_NONE || g_actBox != shownBox) { g_msg = "box signal changed, nothing placed"; ChartRedraw(); return; }
      SetMagicFor(g_actBox);
      if(g_actBox == ACT_BOX) PlaceBoxOrders(); else PlaceReentry();
      g_trade.SetExpertMagicNumber(InpMagicBox);
     }
   else if(sparam == BTN_BOX_SKIP)
     {
      if(g_actBox == ACT_NONE || g_actBox != shownBox) { g_msg = "box signal changed, nothing skipped"; ChartRedraw(); return; }
      if(g_actBox == ACT_BOX) { g_boxDismissed = true; Log("skipped", "box dismissed for today"); }
      else if(g_actBox == ACT_REENTRY) { g_reentryPlaced = true; Log("skipped", "re-entry declined"); }
      SaveState();
     }
   else if(sparam == BTN_TM)
     {
      if(g_actTimed == ACT_NONE || g_actTimed != shownTimed) { g_msg = "signal changed, nothing placed"; ChartRedraw(); return; }
      SetMagicFor(g_actTimed);
      if(g_actTimed == ACT_GOTOBI) PlaceGotobi(); else PlaceM3();
      g_trade.SetExpertMagicNumber(InpMagicBox);
     }
   else if(sparam == BTN_TM_SKIP)
     {
      if(g_actTimed == ACT_NONE || g_actTimed != shownTimed) { g_msg = "signal changed, nothing skipped"; ChartRedraw(); return; }
      if(g_actTimed == ACT_GOTOBI) { g_gotobiDismissed = true; Log("skipped", "gotobi dismissed for today"); }
      else if(g_actTimed == ACT_M3) { g_m3Dismissed = true; Log("skipped", "M-3 dismissed for today"); }
      SaveState();
     }
   Update();
  }
//+------------------------------------------------------------------+
