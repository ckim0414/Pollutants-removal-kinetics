import io,json,zipfile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import streamlit as st
from analysis import validate,baseline,fit,regression,MODELS,demo

st.set_page_config(page_title='Kinetic Lab',layout='wide')
st.title('Kinetic Lab · 연구실 테스트 버전')
st.caption('농도 데이터 → kinetics → 조건 비교 → 산화제 이용 → 논문 figure')
PALETTES={'Muted':['#6487A2','#C58C65','#789780','#A184A2','#8A8A8A','#B6A46B','#709DA1','#B57882'], 'Pastel':['#91B4D0','#E1B291','#A2C1AA','#BDAACC','#B9B7B1','#D8C88F','#9FCACE','#D4A5B0'],'Colorblind':['#0072B2','#D55E00','#009E73','#CC79A7','#777777','#E69F00','#56B4E9','#A79B00']}
with st.sidebar:
    st.header('공통 그래프 스타일')
    palette=st.selectbox('Palette',list(PALETTES))
    font=st.selectbox('Font',['DejaVu Sans','Arial','Times New Roman'])
    fs=st.number_input('축 제목 크기',6,30,12);ticks=st.number_input('Tick 크기',6,30,10);leg=st.number_input('Legend 크기',6,25,9)
    ms=st.slider('Marker 크기',2.,12.,6.);lw=st.slider('선 두께',.5,3.,1.4)
    width=st.number_input('Panel 너비 (inch)',2.,10.,4.);height=st.number_input('Panel 높이 (inch)',2.,10.,3.3)
    fmt=st.selectbox('Export',['tiff','png','pdf','svg']);dpi=st.selectbox('DPI',[300,600,1200],index=1)
plt.rcParams.update({'font.family':font,'font.size':ticks,'axes.labelsize':fs,'legend.fontsize':leg,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','pdf.fonttype':42})
up=st.file_uploader('CSV / Excel 업로드',type=['csv','xlsx'])
try:
    if up:
        if up.name.endswith('.xlsx'):
            book=pd.ExcelFile(up);sheet=st.selectbox('Sheet',book.sheet_names);raw=pd.read_excel(book,sheet_name=sheet)
        else:raw=pd.read_csv(up)
    else:raw=demo();st.info('예제 데이터로 즉시 테스트할 수 있습니다. 실제 데이터는 농도 변환 후 업로드하세요.')
    st.download_button('예제 CSV 다운로드',demo().to_csv(index=False).encode(),'example_long.csv')
    with st.expander('입력 형식 / Column mapping',expanded=bool(up)):
        st.caption('Long: 한 행 = 조건·독립 반복실험·시간점. Wide: 농도 열 하나 = 조건/반복실험. 산화제는 long 형식에서 지원합니다.')
        form=st.radio('형식',['Long','Wide'],horizontal=True)
        cols=list(raw.columns)
        def mapping(label,default,optional=False):
            choices=['(없음)']+cols if optional else cols
            return st.selectbox(label,choices,index=choices.index(default) if default in choices else 0)
        tc=mapping('Time','time')
        if form=='Long':
            cc=mapping('Condition','condition');rc=mapping('Replicate','replicate',True);pc=mapping('Pollutant','pollutant');oc=mapping('Oxidant','oxidant',True)
            if len({tc,cc,pc}|({rc} if rc!='(없음)' else set())|({oc} if oc!='(없음)' else set())) != 3+(rc!='(없음)')+(oc!='(없음)'):raise ValueError('열 역할은 중복 지정할 수 없습니다.')
            d=pd.DataFrame({'time':raw[tc],'condition':raw[cc],'pollutant':raw[pc],'replicate':raw[rc] if rc!='(없음)' else '1'})
            if oc!='(없음)':d['oxidant']=raw[oc]
        else:
            chosen=st.multiselect('농도 열',[c for c in cols if c!=tc],default=[c for c in cols if c!=tc])
            wm=st.data_editor(pd.DataFrame({'column':chosen,'condition':chosen,'replicate':['1']*len(chosen)}),disabled=['column'],key='wide_map')
            d=pd.concat([pd.DataFrame({'time':raw[tc],'condition':r.condition,'replicate':r.replicate,'pollutant':raw[r.column]}) for r in wm.itertuples()],ignore_index=True)
        extra=[c for c in cols if c not in [tc] and pd.api.types.is_numeric_dtype(raw[c])]
        xc=st.selectbox('숫자 조건 변수 (선택)',['직접 입력']+extra,index=(1+extra.index('rpm')) if 'rpm' in extra and form=='Long' else 0)
    d=validate(d)
except Exception as e:st.error(str(e));st.stop()
conditions=list(d.condition.unique())
meta=pd.DataFrame({'condition':conditions,'x':range(len(conditions)),'label':conditions,'color':[PALETTES[palette][i%8] for i in range(len(conditions))],'marker':[['o','s','^','D','v','P','X','<'][i%8] for i in range(len(conditions))]})
if form=='Long' and xc!='직접 입력':
    for i,c in enumerate(conditions):
        values=pd.to_numeric(raw.loc[raw[cc].astype(str)==c,xc],errors='coerce').dropna().unique()
        if len(values)==1:meta.loc[i,'x']=values[0]
        else:st.warning(f'{c}: 조건 변수 값이 하나가 아닙니다. x를 직접 확인하세요.')
with st.expander('조건별 x / 이름 / 색 / 마커',expanded=True):
    meta=st.data_editor(meta,disabled=['condition'],key='styles_'+palette,hide_index=True)
styles=meta.set_index('condition').to_dict('index')
with st.expander('분석 설정',expanded=True):
    a,b,c=st.columns(3)
    model=a.selectbox('Kinetic model',list(MODELS));norm=b.checkbox('C/C₀ 사용',True);fixed=c.checkbox('A=1 고정 (C/C₀만)',False) and norm
    strategy=a.selectbox('k 추정 방식',['평균 시간곡선 피팅','각 반복실험 별도 피팅'])
    tmin=b.number_input('Fit 시작 시간',value=float(d.time.min()));tmax=c.number_input('Fit 종료 시간',value=float(d.time.max()))
    rawpoints=a.checkbox('개별 반복 데이터 표시',False);errors=b.selectbox('k Error bar',['95% CI','SE','반복 k의 SD','없음'])
    timeunit=c.text_input('시간 단위','min');punit=a.text_input('오염물질 농도 단위','mg/L');ounit=b.text_input('산화제 농도 단위','mM');xname=c.text_input('조건 x축 제목','Stirring speed (rpm)')
    st.caption('PFO: C=A exp(−kt); Second-order: C=A/(1+Akt) (농도 기반 2차식); Zero-order: C=A−kt. 시간 원점은 입력 t=0입니다.')
    st.caption('95% CI는 공분산과 t 분포로 계산한 근사 대칭 CI입니다. SE는 피팅 불확실성, SD는 독립 반복실험 간 변동입니다. 반복 k의 CI는 반복 수−1 자유도를 사용합니다.')
try:dp=baseline(d,'pollutant') if norm else d.assign(normalized=d.pollutant)
except Exception as e:st.error(str(e));st.stop()
results=[];curves={};residual=[];failures=[]
from scipy.stats import t as student_t
for cond,g in dp.groupby('condition',sort=False):
    subset=g[g.time.between(tmin,tmax)]
    groups=[('mean',subset.groupby('time',as_index=False).normalized.mean())] if strategy.startswith('평균') else list(subset.groupby('replicate'))
    fitted=[]
    for rep,h in groups:
        try:
            h=h.sort_values('time');r,pred=fit(h.time,h.normalized,model,fixed);r.update(condition=cond,replicate=rep);fitted.append(r)
            residual.extend([{'condition':cond,'replicate':rep,'time':tm,'observed':y,'predicted':yp,'residual':y-yp} for tm,y,yp in zip(h.time,h.normalized,pred)])
        except Exception as e:failures.append(f'{cond}/{rep}: {e}')
    if not fitted:continue
    f=pd.DataFrame(fitted);curves[cond]=fitted
    if strategy.startswith('평균'):summary=fitted[0].copy();summary['SD']=np.nan;summary['n_replicates']=g.replicate.nunique()
    else:
        n=len(f);sd=f.k.std(ddof=1);se=sd/np.sqrt(n);margin=student_t.ppf(.975,n-1)*se if n>1 else np.nan
        summary=dict(condition=cond,k=f.k.mean(),SE=se,SD=sd,CI_low=f.k.mean()-margin,CI_high=f.k.mean()+margin,R2=np.nan,n=f.n.sum(),n_replicates=n)
    results.append(summary)
for msg in failures:st.warning(msg)
summary=pd.DataFrame(results)
if summary.empty:st.error('성공한 피팅이 없습니다. 데이터와 시간 범위를 확인하세요.');st.stop()
st.download_button('k 결과 CSV',summary.to_csv(index=False).encode(),'kinetic_results.csv')
st.download_button('잔차 CSV',pd.DataFrame(residual).to_csv(index=False).encode(),'residuals.csv')
plot_options={}
with st.expander('그래프별 축 설정'):
    st.caption('빈칸은 자동. 범위는 min,max; tick은 양수 숫자. 축 제목을 바꾸려면 각 그래프 설정을 사용하세요.')
    for name in ['Pollutant kinetics','Oxidant kinetics','k comparison','Condition effect','Oxidant utilization','Residuals']:
        cs=st.columns(4);plot_options[name]={'xlabel':cs[0].text_input(name+' x title',key=name+'xt'),'ylabel':cs[1].text_input(name+' y title',key=name+'yt'),'xlim':cs[2].text_input(name+' x min,max',key=name+'xl'),'ylim':cs[3].text_input(name+' y min,max',key=name+'yl')}
        cs=st.columns(2);plot_options[name]['xtick']=cs[0].text_input(name+' x tick',key=name+'xi');plot_options[name]['ytick']=cs[1].text_input(name+' y tick',key=name+'yi')

def style_for(cond):
    s=styles[cond]
    return dict(color=s['color'],marker=s['marker'],label=s['label'],markersize=ms)

def finish(ax,name,xlabel,ylabel,legend=True):
    opts=plot_options[name];ax.set_xlabel(opts['xlabel'] or xlabel);ax.set_ylabel(opts['ylabel'] or ylabel)
    for axis in ['x','y']:
        if opts[axis+'lim']:
            bounds=list(map(float,opts[axis+'lim'].split(',')))
            if len(bounds)!=2 or bounds[0]>=bounds[1]:raise ValueError('축 범위는 min,max (min<max)로 입력하세요.')
            getattr(ax,'set_'+axis+'lim')(bounds)
        if opts[axis+'tick']:
            step=float(opts[axis+'tick'])
            if step<=0:raise ValueError('tick 간격은 양수여야 합니다.')
            getattr(ax,axis+'axis').set_major_locator(MultipleLocator(step))
    ax.tick_params(labelsize=ticks)
    if legend and ax.get_legend_handles_labels()[0]:ax.legend(frameon=False)

def kinetic_plot(ax,col,name):
    source=dp if col=='pollutant' else (baseline(d,'oxidant') if norm else d.assign(normalized=d.oxidant))
    for cond,g in source.groupby('condition',sort=False):
        agg=g.groupby('time').normalized.agg(['mean','std']);s=style_for(cond)
        ax.errorbar(agg.index,agg['mean'],yerr=agg['std'].fillna(0),linestyle='none',capsize=3,**s)
        if rawpoints:ax.scatter(g.time,g.normalized,color=s['color'],marker=s['marker'],alpha=.25,s=ms**2/2)
        if col=='pollutant' and cond in curves:
            xx=np.linspace(tmin,tmax,200)
            for r in curves[cond]:ax.plot(xx,MODELS[model](xx,r['A'],r['k']),color=s['color'],lw=lw,alpha=.8)
    finish(ax,name,f'Time ({timeunit})','C/C₀' if norm else f'{col.capitalize()} ({punit if col=="pollutant" else ounit})')

kind=st.selectbox('조건–k 회귀',['None','Linear','Quadratic'])
bar=st.checkbox('k 비교를 막대그래프로',True)
origin=st.checkbox('Δ농도 회귀를 원점 통과로 제한',False)
molar=st.checkbox('Δ농도를 mol/L로 변환',False)
if molar:
    pMW=st.number_input('오염물질 분자량 (g/mol)',min_value=.001,value=296.15)
    oMW=st.number_input('산화제 분자량 (g/mol)',min_value=.001,value=152.17)
    pu=st.selectbox('오염물질 입력 단위',['mg/L','µg/L','mM','µM','mol/L'])
    ou=st.selectbox('산화제 입력 단위',['mM','mg/L','µg/L','µM','mol/L'])
    def factor(unit,mw):return {'mg/L':1e-3/mw,'µg/L':1e-6/mw,'mM':1e-3,'µM':1e-6,'mol/L':1}[unit]

regtables=[]
def kplot(ax,effect=False):
    for i,r in enumerate(summary.itertuples()):
        s=style_for(r.condition);xx=float(styles[r.condition]['x']) if effect else i
        err=None
        if errors=='95% CI' and np.isfinite(r.CI_low):err=np.array([[r.k-r.CI_low],[r.CI_high-r.k]])
        elif errors=='SE' and np.isfinite(r.SE):err=r.SE
        elif errors=='반복 k의 SD' and np.isfinite(r.SD):err=r.SD
        if not effect and bar:ax.bar(xx,r.k,color=s['color'],width=.65);ax.errorbar(xx,r.k,yerr=err,fmt='none',color='#333333',capsize=3)
        else:ax.errorbar(xx,r.k,yerr=err,linestyle='none',capsize=3,**s)
    if effect and kind!='None':
        xx=np.array([float(styles[c]['x']) for c in summary.condition]);tab,fn,r2=regression(xx,summary.k,kind)
        grid=np.linspace(xx.min(),xx.max(),200);ax.plot(grid,fn(grid),color='#555555',lw=lw);ax.text(.04,.96,f'R² = {r2:.3f}',transform=ax.transAxes,va='top');regtables.append(('condition',tab))
    if not effect:ax.set_xticks(range(len(summary)),[styles[c]['label'] for c in summary.condition],rotation=25,ha='right')
    ku=f'{timeunit}⁻¹' if model=='PFO' else (f'({"C/C₀" if norm else punit})⁻¹ {timeunit}⁻¹' if model=='Second-order' else f'{"C/C₀" if norm else punit} {timeunit}⁻¹')
    finish(ax,'Condition effect' if effect else 'k comparison',xname if effect else 'Condition',f'k ({ku})',effect)

delta=None
if 'oxidant' in d:
    try:
        dd=baseline(d,'pollutant');dd['delta_pollutant']=dd['delta'];dd=baseline(dd,'oxidant');dd['delta_oxidant']=dd['delta'];delta=dd
        if molar:delta['delta_pollutant']*=factor(pu,pMW);delta['delta_oxidant']*=factor(ou,oMW)
        st.download_button('Δ농도 CSV',delta.to_csv(index=False).encode(),'delta_concentrations.csv')
        st.caption('Δ농도는 같은 condition/replicate의 t=0 농도를 기준으로 계산합니다. 시간점은 업로드 행에서 짝지어져 있어야 합니다. 기본 Δ회귀는 시간별 평균을 사용하며, x 오차와 공통 C₀로 인한 상관은 모델링하지 않는 탐색적 OLS입니다.')
    except Exception as e:st.warning(str(e))

def utilization(ax):
    for cond,g in delta.groupby('condition',sort=False):
        g=g.groupby('time')[['delta_oxidant','delta_pollutant']].mean().dropna()
        ax.plot(g.delta_oxidant,g.delta_pollutant,linestyle='none',**style_for(cond))
        try:
            tab,fn,r2=regression(g.delta_oxidant,g.delta_pollutant,origin=origin);xx=np.linspace(g.delta_oxidant.min(),g.delta_oxidant.max(),100);ax.plot(xx,fn(xx),color=styles[cond]['color'],lw=lw);regtables.append((cond,tab.assign(R2=r2)))
        except Exception as e:st.warning(f'{cond} Δ회귀: {e}')
    finish(ax,'Oxidant utilization',f'ΔOxidant ({"mol/L" if molar else ounit})',f'ΔPollutant ({"mol/L" if molar else punit})')

def residualplot(ax):
    for cond,g in pd.DataFrame(residual).groupby('condition',sort=False):ax.plot(g.time,g.residual,linestyle='none',**style_for(cond))
    ax.axhline(0,color='#777777',lw=lw);finish(ax,'Residuals',f'Time ({timeunit})','Residual')
plots={'Pollutant kinetics':lambda ax:kinetic_plot(ax,'pollutant','Pollutant kinetics'),'k comparison':lambda ax:kplot(ax),'Condition effect':lambda ax:kplot(ax,True),'Residuals':residualplot}
if 'oxidant' in d:plots['Oxidant kinetics']=lambda ax:kinetic_plot(ax,'oxidant','Oxidant kinetics')
if delta is not None:plots['Oxidant utilization']=utilization

def export(fig):
    buf=io.BytesIO();fig.savefig(buf,format=fmt,dpi=dpi,bbox_inches='tight',facecolor='white');return buf.getvalue()

tabs=st.tabs(['① Kinetics','② Condition Effect','③ Oxidant Utilization','④ Figure Builder'])
try:
    for tab,names in zip(tabs[:3],[['Pollutant kinetics','Residuals'],['k comparison','Condition effect'],['Oxidant kinetics','Oxidant utilization']]):
        with tab:
            if tab==tabs[0]:st.dataframe(summary,hide_index=True)
            for name in names:
                if name not in plots:continue
                fig,ax=plt.subplots(figsize=(width,height));plots[name](ax);fig.tight_layout();st.pyplot(fig);st.download_button(name+' 저장',export(fig),name.replace(' ','_')+'.'+fmt,key=name+'download');plt.close(fig)
    with tabs[3]:
        selected=st.multiselect('Panel 순서',list(plots),default=[n for n in ['Pollutant kinetics','Condition effect','Oxidant kinetics','Oxidant utilization'] if n in plots])
        ncol=st.selectbox('열 수',[1,2,3],index=1);spacing=st.slider('Panel 간격',.2,1.,.45);labels=st.checkbox('(a), (b) Panel 이름',True)
        if selected:
            nrow=int(np.ceil(len(selected)/ncol));fig,axs=plt.subplots(nrow,ncol,figsize=(width*ncol,height*nrow),squeeze=False)
            for i,ax in enumerate(axs.flat):
                if i>=len(selected):ax.set_visible(False);continue
                plots[selected[i]](ax)
                if labels:ax.text(-.15,1.07,f'({chr(97+i)})',transform=ax.transAxes,fontweight='bold',fontsize=fs+2)
            fig.subplots_adjust(wspace=spacing,hspace=spacing);st.pyplot(fig);st.download_button('완성 Figure 저장',export(fig),'publication_figure.'+fmt);plt.close(fig)
except Exception as e:st.error('그래프 설정 확인: '+str(e))
if regtables:
    with st.expander('회귀 계수 / slope 결과'):
        for name,table in regtables[:len(conditions)+1]:st.write(name);st.dataframe(table,hide_index=True)
        rt=pd.concat([tb.assign(group=nm) for nm,tb in regtables]).drop_duplicates()
        st.download_button('회귀 결과 CSV',rt.to_csv(index=False).encode(),'regression_results.csv')
if errors=='반복 k의 SD' and strategy.startswith('평균'):st.warning('반복 k의 SD는 각 반복실험 별도 피팅을 선택해야 표시됩니다.')
settings={'version':'0.1','model':model,'normalization':norm,'fixed_A':fixed,'strategy':strategy,'fit_range':[tmin,tmax],'palette':palette,'styles':meta.to_dict('records'),'font':font,'label_size':fs,'tick_size':ticks,'legend_size':leg,'marker_size':ms,'line_width':lw,'time_unit':timeunit,'pollutant_unit':punit,'oxidant_unit':ounit,'axis_options':plot_options}
bundle=io.BytesIO()
with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('input_canonical.csv',d.to_csv(index=False));z.writestr('kinetic_results.csv',summary.to_csv(index=False));z.writestr('individual_fits.csv',pd.concat([pd.DataFrame(v) for v in curves.values()]).to_csv(index=False));z.writestr('residuals.csv',pd.DataFrame(residual).to_csv(index=False));z.writestr('settings.json',json.dumps(settings,ensure_ascii=False,indent=2))
    if delta is not None:z.writestr('delta_concentrations.csv',delta.to_csv(index=False))
st.download_button('분석 기록 ZIP (데이터·설정·결과)',bundle.getvalue(),'analysis_record.zip')
