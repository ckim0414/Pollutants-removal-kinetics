import io,json,zipfile,hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import MultipleLocator
from matplotlib.colors import is_color_like
from scipy.stats import t as student_t
import streamlit as st
from analysis import validate,baseline,fit,regression,MODELS,demo

st.set_page_config(page_title='Kinetic Lab',layout='wide')
st.title('Kinetic Lab v0.4')
st.caption('농도 입력 · 독립적인 오염물질/산화제 분석 · 일관된 논문 figure')
PALETTES={'Muted':['#6487A2','#C58C65','#789780','#A184A2','#8A8A8A','#B6A46B','#709DA1','#B57882'],'Colorblind':['#0072B2','#D55E00','#009E73','#CC79A7','#777777','#E69F00','#56B4E9','#A79B00'],'Deep muted':['#334E68','#356D69','#9A5348','#777548','#765A79','#586675','#986E3F','#805766']}
MARKERS={'○ 원':'o','□ 사각형':'s','△ 위 삼각형':'^','▽ 아래 삼각형':'v','◇ 마름모':'D','⬡ 육각형':'h','◁ 왼쪽 삼각형':'<','▷ 오른쪽 삼각형':'>'}

# All user-facing options use stable keys. Restore before any option widgets exist.
with st.sidebar:
    st.header('설정 파일')
    cfgup=st.file_uploader('설정 JSON 불러오기',type=['json'],key='_config_file')
    if st.button('설정 적용',disabled=cfgup is None):
        try:
            payload=json.loads(cfgup.getvalue());widgets=payload['widgets'];savedstyles=payload.get('styles',[])
            if payload.get('version') not in ['0.2','0.3','0.4'] or not isinstance(widgets,dict) or not isinstance(savedstyles,list):raise ValueError('v0.2~v0.4 설정 파일이 필요합니다.')
            allowed=('global_','p_','o_','plot_','effect_','util_','builder_','units_')
            for key in list(st.session_state):
                if key.startswith(allowed) or key.startswith('style_editor_'):del st.session_state[key]
            for key,value in widgets.items():
                if key.startswith(allowed):st.session_state[key]=value
            st.session_state['_restored_styles']=savedstyles
            st.session_state['_restored_palette']=widgets.get('global_palette','Muted')
            st.success('설정을 적용했습니다. 데이터는 별도로 업로드하세요.')
        except Exception as e:st.error(str(e))
    st.header('공통 그래프 스타일')
    palette=st.selectbox('Palette',list(PALETTES),key='global_palette')
    available_fonts=sorted({f.name for f in font_manager.fontManager.ttflist if 'Display' not in f.name})
    preferred=[f for f in ['DejaVu Sans','DejaVu Serif','Arial','Times New Roman','Calibri','Malgun Gothic','Nimbus Sans','Nimbus Roman'] if f in available_fonts]
    font_choices=preferred+[f for f in available_fonts if f not in preferred]
    if st.session_state.get('global_font',font_choices[0]) not in font_choices:
        st.warning('저장된 폰트가 이 PC에 없어 DejaVu Sans로 변경합니다.')
        st.session_state['global_font']='DejaVu Sans'
    font=st.selectbox('Font (설치된 폰트)',font_choices,key='global_font')
    st.caption('실제 설치된 폰트만 표시합니다. Serif를 선택하면 변화가 쉽게 보입니다.')
    fs=st.number_input('축 제목 크기',6,30,12,key='global_fs');ticks=st.number_input('눈금 크기',6,30,10,key='global_ticks');leg=st.number_input('Legend 크기',6,25,9,key='global_leg')
    ms=st.slider('마커 크기',2.,12.,6.,key='global_ms');edge=st.slider('마커 테두리 두께',.3,3.,1.2,key='global_edge');lw=st.slider('선 두께',.5,3.,1.4,key='global_lw')
    boxed=st.checkbox('상단·오른쪽 테두리 표시',True,key='global_box')
    width=st.number_input('Panel 너비 (inch)',2.,10.,4.,key='global_width');height=st.number_input('Panel 높이 (inch)',2.,10.,3.3,key='global_height')
    fmt=st.selectbox('Export',['tiff','png','pdf','svg'],key='global_fmt');dpi=st.selectbox('DPI',[300,600,1200],index=1,key='global_dpi')
plt.rcParams.update({'font.family':font,'font.size':ticks,'axes.labelsize':fs,'legend.fontsize':leg,'axes.spines.top':boxed,'axes.spines.right':boxed,'svg.fonttype':'none','pdf.fonttype':42})
tabs=st.tabs(['① 데이터 입력','② 오염물질 분석','③ 산화제 분석','④ 조건 비교','⑤ 산화제 이용','⑥ Figure Builder'])
with tabs[0]:
    up=st.file_uploader('CSV / Excel 업로드',type=['csv','xlsx'])
    try:
        if up:
            if up.name.endswith('.xlsx'):
                book=pd.ExcelFile(up);sheet=st.selectbox('Sheet',book.sheet_names);raw=pd.read_excel(book,sheet_name=sheet)
            else:raw=pd.read_csv(up)
        else:raw=demo();st.info('예제 데이터를 표시합니다. 실제 농도는 외부표준 환산·희석 보정 후 업로드하세요.')
        st.download_button('예제 CSV',demo().to_csv(index=False).encode(),'example_long.csv')
        with st.expander('입력 형식 / 열 역할 지정',expanded=True):
            form=st.radio('형식',['Long','Wide'],horizontal=True)
            cols=list(raw.columns)
            def mapping(label,default,optional=False):
                choices=['(없음)']+cols if optional else cols
                return st.selectbox(label,choices,index=choices.index(default) if default in choices else 0)
            tc=mapping('Time','time')
            if form=='Long':
                cc=mapping('Condition','condition');rc=mapping('Replicate','replicate',True);pc=mapping('Pollutant','pollutant');oc=mapping('Oxidant','oxidant',True)
                roles=[tc,cc,pc]+([rc] if rc!='(없음)' else [])+([oc] if oc!='(없음)' else [])
                if len(set(roles))!=len(roles):raise ValueError('같은 열에 여러 역할을 지정할 수 없습니다.')
                d=pd.DataFrame({'time':raw[tc],'condition':raw[cc],'replicate':raw[rc] if rc!='(없음)' else '1','pollutant':raw[pc]})
                if oc!='(없음)':d['oxidant']=raw[oc]
                extra=[c for c in cols if c not in roles and pd.api.types.is_numeric_dtype(raw[c])]
                xc=st.selectbox('숫자 조건 변수',['직접 입력']+extra,index=1+extra.index('rpm') if 'rpm' in extra else 0)
            else:
                chosen=st.multiselect('농도 열',[c for c in cols if c!=tc],default=[c for c in cols if c!=tc])
                if not chosen:raise ValueError('농도 열을 선택하세요.')
                wm=st.data_editor(pd.DataFrame({'column':chosen,'condition':chosen,'replicate':['1']*len(chosen)}),disabled=['column'],key='wide_map')
                d=pd.concat([pd.DataFrame({'time':raw[tc],'condition':r.condition,'replicate':r.replicate,'pollutant':raw[r.column]}) for r in wm.itertuples()],ignore_index=True)
                xc='직접 입력';st.caption('산화제를 함께 분석하려면 Long 형식을 사용하세요.')
        d=validate(d)
    except Exception as e:st.error(str(e));st.stop()
    conditions=list(d.condition.unique())
    meta=pd.DataFrame({'condition':conditions,'x':np.arange(len(conditions),dtype=float),'label':conditions,'color':[PALETTES[palette][i%8] for i in range(len(conditions))],'marker':[list(MARKERS)[i%8] for i in range(len(conditions))],'fill':['Open']*len(conditions)})
    if form=='Long' and xc!='직접 입력':
        for i,c in enumerate(conditions):
            vals=pd.to_numeric(raw.loc[raw[cc].astype(str)==c,xc],errors='coerce').dropna().unique()
            if len(vals)==1:meta.loc[i,'x']=vals[0]
            else:st.warning(f'{c}: 조건 변수 값이 하나가 아닙니다. x를 직접 확인하세요.')
    restored={r['condition']:r for r in st.session_state.get('_restored_styles',[]) if isinstance(r,dict) and 'condition' in r}
    if st.session_state.get('_restored_palette',palette)!=palette:restored={}
    for i,c in enumerate(conditions):
        if c in restored:
            for col in ['x','label','color','marker','fill']:
                if col in restored[c]:meta.loc[i,col]=restored[c][col]
    signature=hashlib.sha256((''.join(conditions)+palette).encode()).hexdigest()[:12]
    st.subheader('조건 스타일 · 모든 패널에서 공유')
    meta=st.data_editor(meta,hide_index=True,disabled=['condition'],key='style_editor_'+signature,column_config={'marker':st.column_config.SelectboxColumn('마커',options=list(MARKERS),required=True),'fill':st.column_config.SelectboxColumn('채움',options=['Open','Hollow','Filled'],required=True)})
    if not all(is_color_like(c) for c in meta.color) or not meta.marker.isin(MARKERS).all() or not meta.fill.isin(['Open','Hollow','Filled']).all():st.error('색(HEX), 마커, 채움을 확인하세요.');st.stop()
    if not np.isfinite(pd.to_numeric(meta.x,errors='coerce')).all():st.error('조건 x값은 유한한 숫자여야 합니다.');st.stop()
    styles=meta.set_index('condition').to_dict('index')
    st.caption('Open=흰색 채움, Hollow=투명, Filled=색 채움. 같은 마커·색을 지정하고 채움만 바꾸면 관련 실험을 묶을 수 있습니다. 독립 batch 반복과 기기 반복주입을 구분하세요.')
    with st.expander('단위'):
        timeunit=st.text_input('시간 단위','min',key='units_time');punit=st.text_input('오염물질 농도 단위','mg/L',key='units_p');ounit=st.text_input('산화제 농도 단위','mM',key='units_o')
    st.dataframe(d.head(20),hide_index=True)

analyses={};options={};plots={};regtables=[]
def marker_style(cond):
    s=styles[cond]
    return dict(color=s['color'],marker=MARKERS[s['marker']],label=s['label'],markersize=ms,markeredgewidth=edge,markeredgecolor=s['color'],markerfacecolor=('none' if s['fill']=='Hollow' else 'white' if s['fill']=='Open' else s['color']))

def graph_settings(name,default_legend=True):
    prefix='plot_'+name+'_'
    with st.expander('그래프 설정 · '+name):
        cs=st.columns(3)
        legend=cs[0].checkbox('Legend 표시',default_legend,key=prefix+'legend');loc=cs[1].selectbox('Legend 위치',['best','upper right','upper left','lower right','lower left','center right','center left','upper center','lower center'],key=prefix+'loc');points=cs[2].checkbox('실험점 표시',True,key=prefix+'points')
        cs=st.columns(2);lines=cs[0].checkbox('피팅선 표시',True,key=prefix+'lines');equation=cs[1].checkbox('회귀식 표시',False,key=prefix+'equation')
        cs=st.columns(2);xlabel=cs[0].text_input('X축 제목 (빈칸=자동)',key=prefix+'xlabel');ylabel=cs[1].text_input('Y축 제목 (빈칸=자동)',key=prefix+'ylabel')
        st.caption('첨자: $S_2O_8^{2-}$ · $C/C_0$ · $k$ ($min^{-1}$). 달러 기호를 포함해 입력하세요.')
        if xlabel or ylabel:
            preview,ax=plt.subplots(figsize=(4,1));ax.axis('off');ax.text(.01,.65,xlabel or 'X axis');ax.text(.01,.15,ylabel or 'Y axis')
            try:st.pyplot(preview)
            except Exception as e:st.warning('첨자 문법 확인: '+str(e))
            finally:plt.close(preview)
        cs=st.columns(2);xlim=cs[0].text_input('X축 범위 min,max',key=prefix+'xlim');ylim=cs[1].text_input('Y축 범위 min,max',key=prefix+'ylim')
        cs=st.columns(2);xtick=cs[0].text_input('X축 눈금 간격',help='예: 10 → 10 단위 간격. 빈칸은 자동.',key=prefix+'xtick');ytick=cs[1].text_input('Y축 눈금 간격',help='양수 숫자. 빈칸은 자동.',key=prefix+'ytick')
    options[name]=dict(legend=legend,loc=loc,points=points,lines=lines,equation=equation,xlabel=xlabel,ylabel=ylabel,xlim=xlim,ylim=ylim,xtick=xtick,ytick=ytick)

def finish(ax,name,xlabel,ylabel):
    op=options[name];ax.set_xlabel(op['xlabel'] or xlabel,fontfamily=font);ax.set_ylabel(op['ylabel'] or ylabel,fontfamily=font)
    for axis in ['x','y']:
        if op[axis+'lim']:
            bounds=list(map(float,op[axis+'lim'].split(',')))
            if len(bounds)!=2 or bounds[0]>=bounds[1]:raise ValueError('축 범위는 min,max (min<max)로 입력하세요.')
            getattr(ax,'set_'+axis+'lim')(bounds)
        if op[axis+'tick']:
            step=float(op[axis+'tick'])
            if not np.isfinite(step) or step<=0:raise ValueError('눈금 간격은 유한한 양수여야 합니다.')
            getattr(ax,axis+'axis').set_major_locator(MultipleLocator(step))
    ax.tick_params(top=False,right=False,labelsize=ticks)
    for text in ax.get_xticklabels()+ax.get_yticklabels()+ax.texts:
        text.set_fontfamily(font)
    if op['legend'] and ax.get_legend_handles_labels()[0]:ax.legend(frameon=False,loc=op['loc'],prop={'family':font,'size':leg})

def show_figure(fig):
    # Explicit image bytes ensure the display uses the same updated Figure as export.
    preview_bytes=io.BytesIO();fig.savefig(preview_bytes,format='png',dpi=150,bbox_inches='tight',facecolor='white')
    st.image(preview_bytes.getvalue())

def render(name):
    fig,ax=plt.subplots(figsize=(width,height))
    try:
        plots[name](ax);fig.tight_layout();show_figure(fig)
        buf=io.BytesIO();fig.savefig(buf,format=fmt,dpi=dpi,bbox_inches='tight',facecolor='white');st.download_button('그래프 저장 · '+name,buf.getvalue(),name.replace(' ','_')+'.'+fmt,key='download_'+name)
    except Exception as e:st.error(name+': '+str(e))
    finally:plt.close(fig)

def calculate(col,cfg):
    source=baseline(d,col) if cfg['norm'] else d.assign(normalized=d[col]);result=[];curves={};residual=[];failures=[]
    if cfg['model']=='None':return dict(source=source,summary=pd.DataFrame(),curves=curves,residual=pd.DataFrame(),cfg=cfg,failures=[])
    for cond,g in source.groupby('condition',sort=False):
        subset=g[g.time.between(cfg['tmin'],cfg['tmax'])]
        groups=[('mean',subset.groupby('time',as_index=False).normalized.mean())] if cfg['strategy']=='mean' else list(subset.groupby('replicate'))
        fitted=[]
        for rep,h in groups:
            try:
                h=h.sort_values('time');r,pred=fit(h.time,h.normalized,cfg['model'],cfg['fixed']);r.update(condition=cond,replicate=rep);fitted.append(r)
                residual.extend([dict(condition=cond,replicate=rep,time=tm,observed=y,predicted=yp,residual=y-yp) for tm,y,yp in zip(h.time,h.normalized,pred)])
            except Exception as e:failures.append(f'{cond}/{rep}: {e}')
        if not fitted:continue
        f=pd.DataFrame(fitted);curves[cond]=fitted
        if cfg['strategy']=='mean':r=fitted[0].copy();r.update(SD=np.nan,n_replicates=g.replicate.nunique())
        else:
            n=len(f);sd=f.k.std(ddof=1);se=sd/np.sqrt(n);margin=student_t.ppf(.975,n-1)*se if n>1 else np.nan
            r=dict(condition=cond,k=f.k.mean(),SE=se,SD=sd,CI_low=f.k.mean()-margin,CI_high=f.k.mean()+margin,R2=np.nan,n=f.n.sum(),n_replicates=n)
        result.append(r)
    return dict(source=source,summary=pd.DataFrame(result),curves=curves,residual=pd.DataFrame(residual),cfg=cfg,failures=failures)

def kinetics(ax,col,name):
    a=analyses[col];cfg=a['cfg'];op=options[name]
    for cond,g in a['source'].groupby('condition',sort=False):
        agg=g.groupby('time').normalized.agg(['mean','std']);s=marker_style(cond)
        if op['points']:
            ax.errorbar(agg.index,agg['mean'],yerr=agg['std'].fillna(0),linestyle='none',capsize=3,**s)
            if cfg['raw']:
                ax.plot(g.time,g.normalized,linestyle='none',alpha=.3,**{**s,'label':'_nolegend_','markersize':ms*.7})
        if op['lines'] and cond in a['curves']:
            xx=np.linspace(cfg['tmin'],cfg['tmax'],200)
            for r in a['curves'][cond]:ax.plot(xx,MODELS[cfg['model']](xx,r['A'],r['k']),color=s['color'],lw=lw,label=s['label'] if not op['points'] else '_nolegend_')
    if op['equation'] and cfg['model']!='None':ax.text(.03,.97,{'PFO':r'$C=Ae^{-kt}$','Second-order':r'$C=A/(1+Akt)$','Zero-order':r'$C=A-kt$'}[cfg['model']],transform=ax.transAxes,va='top')
    finish(ax,name,f'Time ({timeunit})',r'$C/C_0$' if cfg['norm'] else f'{col.capitalize()} ({punit if col=="pollutant" else ounit})')

def residualplot(ax,col,name):
    if options[name]['points']:
        for cond,g in analyses[col]['residual'].groupby('condition',sort=False):ax.plot(g.time,g.residual,linestyle='none',**marker_style(cond))
    ax.axhline(0,color='#777777',lw=lw);finish(ax,name,f'Time ({timeunit})','Residual')

for col,tab,prefix in [('pollutant',tabs[1],'p_'),('oxidant',tabs[2],'o_')]:
    with tab:
        if col not in d:st.info('산화제 농도 열이 없습니다. 데이터 입력에서 지정하세요.');continue
        with st.expander('분석 설정',expanded=True):
            cs=st.columns(3);model=cs[0].selectbox('Kinetic model',['None']+list(MODELS),index=1 if col=='pollutant' else 0,key=prefix+'model');norm=cs[1].checkbox('C/C₀ 사용',True,key=prefix+'norm');fixed=cs[2].checkbox('A=1 고정 (정규화 시)',False,key=prefix+'fixed') and norm
            cs=st.columns(3);strategy=cs[0].selectbox('k 추정 방식',['평균 시간곡선 피팅','각 반복실험 별도 피팅'],key=prefix+'strategy');tmin=cs[1].number_input('Fit 시작 시간',value=float(d.time.min()),key=prefix+'tmin');tmax=cs[2].number_input('Fit 종료 시간',value=float(d.time.max()),key=prefix+'tmax')
            rawpoints=st.checkbox('개별 반복 데이터 표시',False,key=prefix+'raw')
            st.caption('PFO: C=A exp(−kt) · Second-order: C=A/(1+Akt) · Zero-order: C=A−kt. 시간 원점 t=0. SE·피팅 CI와 독립 반복 k의 SD는 구분합니다.')
        cfg=dict(model=model,norm=norm,fixed=fixed,strategy='mean' if strategy.startswith('평균') else 'replicate',tmin=tmin,tmax=tmax,raw=rawpoints)
        try:
            if tmin>=tmax:raise ValueError('피팅 종료 시간은 시작 시간보다 커야 합니다.')
            a=calculate(col,cfg);analyses[col]=a
        except Exception as e:st.error(str(e));continue
        for message in a['failures']:st.warning(message)
        if model=='None':st.info('회귀 꺼짐 · 실험 농도만 표시합니다.')
        elif a['summary'].empty:st.warning('피팅 실패 · 시간 범위와 데이터를 확인하세요.')
        else:
            st.success(f'피팅 성공 · {len(a["summary"])}개 조건 · k_{col}')
            st.dataframe(a['summary'].rename(columns={'k':'k_'+col}),hide_index=True)
            st.download_button('k 결과 CSV',a['summary'].to_csv(index=False).encode(),f'kinetic_{col}.csv',key=prefix+'csv')
        name=col.capitalize()+' kinetics';graph_settings(name);plots[name]=lambda ax,col=col,name=name:kinetics(ax,col,name);render(name)
        if not a['residual'].empty:
            name=col.capitalize()+' residuals';graph_settings(name,False);plots[name]=lambda ax,col=col,name=name:residualplot(ax,col,name)
            with st.expander('잔차 확인'):render(name)

def coefficient_table(table):
    return table.assign(term=table.term.map({'x^0':'Intercept','x^1':'Slope','x^2':'Quadratic coefficient'}))

def equation_text(table,r2):
    values=dict(zip(table.term,table.estimate));a=values.get('x^0',0);b=values.get('x^1',0);c=values.get('x^2')
    return f'y = {a:.4g} {b:+.4g} x'+(f' {c:+.4g} x²' if c is not None else '')+f'\nR² = {r2:.3f}'

def k_unit(col):
    cfg=analyses[col]['cfg'];cu='C/C₀' if cfg['norm'] else (punit if col=='pollutant' else ounit)
    if cfg['model']=='PFO':return f'{timeunit}⁻¹'
    if cfg['model']=='Second-order':return f'({cu})⁻¹ {timeunit}⁻¹'
    return f'{cu} {timeunit}⁻¹'

def kplot(ax,col,name,opts,effect,reg):
    summary=analyses[col]['summary'];op=options[name]
    if op['points']:
        for i,r in enumerate(summary.itertuples()):
            s=marker_style(r.condition);xx=float(styles[r.condition]['x']) if effect else i;err=None
            if opts['error']=='95% CI' and np.isfinite(r.CI_low):err=np.array([[r.k-r.CI_low],[r.CI_high-r.k]])
            elif opts['error']=='SE' and np.isfinite(r.SE):err=r.SE
            elif opts['error']=='반복 k의 SD' and np.isfinite(r.SD):err=r.SD
            if not effect and opts['bar']:
                ax.bar(xx,r.k,color=s['color'],width=.65);ax.errorbar(xx,r.k,yerr=err,fmt='none',color='#333333',capsize=3)
            else:ax.errorbar(xx,r.k,yerr=err,linestyle='none',capsize=3,**s)
    if effect and reg is not None:
        table,fn,r2=reg;xx=np.array([float(styles[c]['x']) for c in summary.condition]);grid=np.linspace(xx.min(),xx.max(),200)
        if op['lines']:ax.plot(grid,fn(grid),color='#444444',lw=lw)
        if op['equation']:ax.text(.03,.97,equation_text(table,r2),transform=ax.transAxes,va='top',fontsize=ticks)
    if not effect:ax.set_xticks(range(len(summary)),[styles[c]['label'] for c in summary.condition],rotation=25,ha='right')
    finish(ax,name,opts['xname'] if effect else 'Condition',f'k_{col} ({k_unit(col)})')

with tabs[3]:
    st.caption('조건 회귀는 조건별 k에 대한 비가중 회귀입니다. 서로 다른 모델/단위의 k는 직접 비교하지 마세요.')
    for col,a in analyses.items():
        if a['summary'].empty:continue
        st.subheader('오염물질' if col=='pollutant' else '산화제')
        prefix='effect_'+col+'_';cs=st.columns(3)
        kind=cs[0].selectbox('조건–k 회귀',['None','Linear','Quadratic'],key=prefix+'kind');error=cs[1].selectbox('k Error bar',['95% CI','SE','반복 k의 SD','없음'],key=prefix+'error');chart=cs[2].selectbox('k 비교 그래프 형태',['Bar','Scatter'],key=prefix+'chart');bar=chart=='Bar'
        xname=st.text_input('조건 X축 제목','Stirring speed (rpm)',key=prefix+'xname');reg=None
        if error=='반복 k의 SD' and a['cfg']['strategy']=='mean':st.warning('반복 k의 SD는 각 반복실험 별도 피팅에서만 표시됩니다.')
        if bar:st.caption('Bar: 조건 이름으로 비교합니다. Scatter를 선택하면 숫자 조건 x값과 회귀선을 표시합니다.')
        if kind=='None':st.info('조건 회귀 꺼짐 · Linear 또는 Quadratic을 선택하면 선을 계산합니다.')
        else:
            try:
                reg=regression([float(styles[c]['x']) for c in a['summary'].condition],a['summary'].k,kind)
                st.success('조건 회귀 피팅 성공');st.code(equation_text(reg[0],reg[2]),language=None);st.dataframe(coefficient_table(reg[0]),hide_index=True)
                regtables.append(reg[0].assign(group=col+'_condition',R2=reg[2]))
            except Exception as e:st.warning('조건 회귀 피팅 실패: '+str(e))
        opts=dict(error=error,bar=bar,xname=xname)
        effect=not bar
        name=col.capitalize()+' k comparison';graph_settings(name,effect)
        plots[name]=lambda ax,col=col,name=name,opts=opts,effect=effect,reg=reg:kplot(ax,col,name,opts,effect,reg);render(name)

delta=None;utilregs={}
with tabs[4]:
    if 'oxidant' not in d:st.info('산화제 열을 지정하면 이용률 분석이 활성화됩니다.')
    else:
        with st.expander('이용률 분석 설정',expanded=True):
            kind=st.selectbox('Δ농도 회귀',['None','Linear'],index=1,key='util_kind');origin=st.checkbox('원점 통과',False,key='util_origin');molar=st.checkbox('Δ농도를 mol/L로 변환',False,key='util_molar')
            if molar:
                cs=st.columns(2);pMW=cs[0].number_input('오염물질 분자량 (g/mol)',min_value=.001,value=296.15,key='util_pmw');oMW=cs[1].number_input('산화제 분자량 (g/mol)',min_value=.001,value=152.17,key='util_omw')
                cs=st.columns(2);pu=cs[0].selectbox('오염물질 입력 단위',['mg/L','µg/L','mM','µM','mol/L'],key='util_pu');ou=cs[1].selectbox('산화제 입력 단위',['mM','mg/L','µg/L','µM','mol/L'],key='util_ou')
                def factor(unit,mw):return {'mg/L':1e-3/mw,'µg/L':1e-6/mw,'mM':1e-3,'µM':1e-6,'mol/L':1}[unit]
            st.caption('동일 batch의 t=0 기준 Δ농도를 계산하고 시간별 평균을 OLS 회귀합니다. 공통 C₀로 인한 오차 상관과 X축 측정오차는 반영하지 않습니다.')
        try:
            dd=baseline(d,'pollutant');dd['delta_pollutant']=dd['delta'];dd=baseline(dd,'oxidant');dd['delta_oxidant']=dd['delta'];delta=dd
            if molar:delta['delta_pollutant']*=factor(pu,pMW);delta['delta_oxidant']*=factor(ou,oMW)
            if kind!='None':
                for cond,g in delta.groupby('condition',sort=False):
                    agg=g.groupby('time')[['delta_oxidant','delta_pollutant']].mean().dropna()
                    try:
                        reg=regression(agg.delta_oxidant,agg.delta_pollutant,origin=origin);utilregs[cond]=reg
                        st.write(styles[cond]['label']);st.code(equation_text(reg[0],reg[2]),language=None);st.dataframe(coefficient_table(reg[0]),hide_index=True);regtables.append(reg[0].assign(group=cond+'_utilization',R2=reg[2]))
                    except Exception as e:st.warning(cond+' 회귀 실패: '+str(e))
            else:st.info('Δ농도 회귀 꺼짐')
            st.download_button('Δ농도 CSV',delta.to_csv(index=False).encode(),'delta_concentrations.csv')
            name='Oxidant utilization';graph_settings(name)
            def utilization(ax):
                op=options['Oxidant utilization'];eq=[]
                for cond,g in delta.groupby('condition',sort=False):
                    agg=g.groupby('time')[['delta_oxidant','delta_pollutant']].mean().dropna()
                    if op['points']:ax.plot(agg.delta_oxidant,agg.delta_pollutant,linestyle='none',**marker_style(cond))
                    if cond in utilregs:
                        table,fn,r2=utilregs[cond];xx=np.linspace(agg.delta_oxidant.min(),agg.delta_oxidant.max(),100)
                        if op['lines']:ax.plot(xx,fn(xx),color=styles[cond]['color'],lw=lw,label=styles[cond]['label'] if not op['points'] else '_nolegend_')
                        eq.append(styles[cond]['label']+': '+equation_text(table,r2))
                if op['equation']:ax.text(.03,.97,'\n'.join(eq),transform=ax.transAxes,va='top',fontsize=max(6,ticks-2))
                finish(ax,'Oxidant utilization',f'ΔOxidant ({"mol/L" if molar else ounit})',f'ΔPollutant ({"mol/L" if molar else punit})')
            plots[name]=utilization;render(name)
        except Exception as e:st.warning(str(e))
with tabs[5]:
    st.caption('패널별 legend·축·표시 옵션은 각 분석 탭의 그래프 설정을 따릅니다. 선택 순서가 panel 순서입니다.')
    defaults=[n for n in ['Pollutant kinetics','Pollutant k comparison','Oxidant kinetics','Oxidant utilization'] if n in plots]
    # Prevent old selections of a disabled oxidant fit from invalidating the builder.
    if 'builder_selected' in st.session_state:
        renamed=[n.replace(' condition effect',' k comparison') for n in st.session_state['builder_selected']]
        st.session_state['builder_selected']=list(dict.fromkeys(n for n in renamed if n in plots))
    selected=st.multiselect('Panel 순서',list(plots),default=None if 'builder_selected' in st.session_state else defaults,key='builder_selected')
    cs=st.columns(3);ncol=cs[0].selectbox('열 수',[1,2,3],index=1,key='builder_ncol');spacing=cs[1].slider('Panel 간격',.2,1.,.45,key='builder_spacing');labels=cs[2].checkbox('(a), (b) Panel 이름',True,key='builder_labels')
    if selected:
        nrow=int(np.ceil(len(selected)/ncol));fig,axs=plt.subplots(nrow,ncol,figsize=(width*ncol,height*nrow),squeeze=False)
        try:
            for i,ax in enumerate(axs.flat):
                if i>=len(selected):ax.set_visible(False);continue
                plots[selected[i]](ax)
                if labels:ax.text(-.15,1.07,f'({chr(97+i)})',transform=ax.transAxes,fontweight='bold',fontsize=fs+2)
            fig.subplots_adjust(wspace=spacing,hspace=spacing);show_figure(fig);buf=io.BytesIO();fig.savefig(buf,format=fmt,dpi=dpi,bbox_inches='tight',facecolor='white');st.download_button('완성 Figure 저장',buf.getvalue(),'publication_figure.'+fmt)
        except Exception as e:st.error('Figure 설정 확인: '+str(e))
        finally:plt.close(fig)
    allowed=('global_','p_','o_','plot_','effect_','util_','builder_','units_')
    settings={'version':'0.4','widgets':{k:v for k,v in st.session_state.items() if k.startswith(allowed)},'styles':meta.to_dict('records')}
    settings_json=json.dumps(settings,ensure_ascii=False,indent=2)
    st.download_button('설정 JSON 저장',settings_json.encode(),'settings_v04.json')
    bundle=io.BytesIO()
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('input_canonical.csv',d.to_csv(index=False));z.writestr('settings_v04.json',settings_json)
        for col,a in analyses.items():
            z.writestr(f'kinetic_{col}.csv',a['summary'].to_csv(index=False));z.writestr(f'residuals_{col}.csv',a['residual'].to_csv(index=False))
            if a['curves']:z.writestr(f'individual_fits_{col}.csv',pd.concat([pd.DataFrame(v) for v in a['curves'].values()]).to_csv(index=False))
        if delta is not None:z.writestr('delta_concentrations.csv',delta.to_csv(index=False))
        if regtables:z.writestr('regression_results.csv',coefficient_table(pd.concat(regtables,ignore_index=True)).to_csv(index=False))
    st.download_button('분석 기록 ZIP',bundle.getvalue(),'analysis_record.zip')
