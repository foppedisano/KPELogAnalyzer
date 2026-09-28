"""Plot an exported analysis.json; optional Matplotlib is only needed for this script."""
import argparse
import json
from pathlib import Path
from datetime import datetime
from bisect import bisect_left
from itertools import accumulate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('analysis',type=Path)
    args=parser.parse_args()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MultipleLocator
    data=json.loads(args.analysis.read_text(encoding='utf-8'))
    windows=data['windows']
    if not windows or len({w['series_key'] for w in windows})!=1:
        raise ValueError('Il grafico richiede una sola serie non vuota: filtrare observer/device')
    if any(w['percent'] is None for w in windows):
        raise ValueError('Serie con finestre incomplete: rappresentare esplicitamente i valori NULL')
    anchor=datetime.fromisoformat(windows[0]['anchor'])
    starts=[(datetime.fromisoformat(w['start'])-anchor).total_seconds() for w in windows]
    widths=[w['window_ms']/1000 for w in windows]
    values=[w['percent'] for w in windows]
    total=sum(w['window_ms'] for w in windows);occupied=sum(w['underrun_ms'] for w in windows)
    # Detail is selected by occupied duration, never by averaging percentages.
    cumulative=[0]+list(accumulate(w['underrun_ms'] for w in windows))
    best=max(range(len(windows)),key=lambda i:cumulative[bisect_left(starts,starts[i]+60)]-cumulative[i])
    left=starts[best];right=min(starts[-1]+widths[-1],left+60)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,1,figsize=(14,8),gridspec_kw={'height_ratios':[1.3,1]},layout=None)
    fig.patch.set_facecolor('#f6f8fa')
    fig.subplots_adjust(left=.075,right=.975,top=.76,bottom=.16,hspace=.48)
    fig.text(.075,.945,f'Buffer underrun AWT · chiamata #{data["call_id"]}',fontsize=23,weight='bold',color='#152932')
    fig.text(.075,.901,f'{windows[0]["observer"]}  |  ingresso {windows[0]["device"]}  |  {anchor:%d/%m/%Y %H:%M:%S.%f}'[:-3],color='#526776')
    fig.text(.075,.844,f'{len(data["episodes"])} episodi     {occupied/1000:.2f} s ricostruiti     {100*occupied/total:.2f}% del periodo     {len(windows)} finestre',fontsize=13,weight='bold',color='#007f79')
    for ax in axes:
        ax.set_ylim(0,105);ax.set_yticks([0,25,50,75,100]);ax.set_ylabel('Tempo in underrun (%)')
        ax.grid(axis='y',color='#dfe5e9',linewidth=.7);ax.set_axisbelow(True)
        ax.spines['left'].set_color('#bcc9cf');ax.spines['bottom'].set_color('#bcc9cf')
    axes[0].bar([x/60 for x in starts],values,width=[w/60 for w in widths],align='edge',color='#cd6b28',linewidth=0)
    axes[0].set_xlim(0,(starts[-1]+widths[-1])/60);axes[0].xaxis.set_major_locator(MultipleLocator(2))
    axes[0].set_xlabel('Minuti dall’origine delle finestre');axes[0].set_title(f'Intera chiamata · finestre di {max(widths):g} secondi',loc='left',pad=10)
    axes[0].axvspan(left/60,right/60,color='#007f79',alpha=.09)
    for x,y,w in zip(starts,values,widths):
        if x<right and x+w>left:axes[1].bar(x,y,width=w,align='edge',color='#cd6b28',edgecolor='white',linewidth=.3)
    axes[1].set_xlim(left,right);axes[1].xaxis.set_major_locator(MultipleLocator(10))
    axes[1].set_xlabel('Secondi dalla connessione');axes[1].set_title('Dettaglio · intervallo di 60 secondi con più tempo ricostruito in underrun',loc='left',pad=10)
    basis=windows[0]['placement_basis']
    note='Durata dichiarata dal motore, collocata a ritroso dal messaggio di fine.' if basis=='reported_end' else 'Intervallo fra i timestamp dei messaggi nei log.'
    fig.text(.075,.064,note+' Sovrapposizioni conteggiate una volta.',fontsize=10,color='#526776')
    fig.text(.075,.034,'Posizione temporale stimata. Zero = nessun underrun chiuso ricostruito; non certifica audio senza problemi. Ultima finestra normalizzata sulla durata effettiva.',fontsize=9,color='#526776')
    for suffix in ('png','svg'):
        fig.savefig(args.analysis.with_name('underrun-awt.'+suffix),dpi=160,facecolor=fig.get_facecolor())
    plt.close(fig)


if __name__=='__main__':main()
