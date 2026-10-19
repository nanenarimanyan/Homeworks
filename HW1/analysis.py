import numpy as np,pandas as pd,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.optimize import least_squares
from pathlib import Path
R=Path(__file__).resolve().parent
D=pd.read_csv(R/'data/sustainable_cotton.csv')
t=D.year.to_numpy()-2010+1
s=D.share_percent.to_numpy()/100
# fit level of penetration, allow 2010 to be first observation after launch
# F(0)=0, M denotes asymptotic fraction of total production

def F(t,p,q):
 e=np.exp(-(p+q)*np.asarray(t));return (1-e)/(1+(q/p)*e)
def fun(x):return x[2]*F(t,x[0],x[1])-s
fit=least_squares(fun,[.004,.5,.5],bounds=([.00001,.00001,.251],[.5,3,1]),max_nfev=20000)
p,q,M=fit.x
D['fitted_share_percent']=100*M*F(t,p,q)
D.to_csv(R/'data/proxy_fit.csv',index=False)
# Transfer p and q, do not transfer market size: forecast fractions of addressable denim producers.
# illustrative addressable denim brands/mills: 1000 organizations (not an observed count)
N=1000; years=np.arange(2025,2041); T=years-2025+1
cum=N*F(T,p,q); annual=np.diff(np.r_[0,cum]);
forecast=pd.DataFrame({'year':years,'new_adopters_scenario':np.rint(annual).astype(int),'cumulative_adopters_scenario':np.rint(cum).astype(int),'penetration_percent':100*F(T,p,q)})
forecast.to_csv(R/'data/forecast.csv',index=False)
plt.figure(figsize=(8,4.4));plt.plot(D.year,D.share_percent,'o-',label='OECD observed sustainable cotton share');plt.plot(D.year,D.fitted_share_percent,'--',label='Bass fitted share');plt.ylabel('Percent of world cotton output');plt.xlabel('Year');plt.legend();plt.tight_layout();plt.savefig(R/'img/proxy_fit.png',dpi=180);plt.close()
plt.figure(figsize=(8,4.4));plt.bar(years,annual,label='New adopting organizations');plt.plot(years,cum,label='Cumulative adopters',marker='o');plt.ylabel('Organizations (illustrative N=1,000)');plt.xlabel('Year');plt.legend();plt.tight_layout();plt.savefig(R/'img/forecast.png',dpi=180);plt.close()
# market potential sensitivity
sens=[]
for n in [500,1000,2000]:
 for yr in [2030,2035,2040]:
  tt=yr-2025+1;sens.append({'assumed_market_organizations':n,'year':yr,'cumulative_adopters':round(n*F(tt,p,q))})
pd.DataFrame(sens).to_csv(R/'data/sensitivity.csv',index=False)
print('p,q,Mproxy,RMSE percentage points:',p,q,M,np.sqrt(np.mean(fun(fit.x)**2))*100)
print(forecast.to_string(index=False))
