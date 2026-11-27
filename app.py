"""Tarot o' Mine: independent Python card engine and Streamlit UI."""
import secrets
import json
from datetime import datetime, timezone
from uuid import uuid4
from copy import deepcopy

MAJORS = 'The Fool|The Magician|The High Priestess|The Empress|The Emperor|The Hierophant|The Lovers|The Chariot|Strength|The Hermit|Wheel of Fortune|Justice|The Hanged Man|Death|Temperance|The Devil|The Tower|The Star|The Moon|The Sun|Judgement|The World'.split('|')
MINORS = [f'{r} of {s}' for s in ('Wands','Cups','Swords','Pentacles') for r in ['Ace',*map(str,range(2,11)),'Page','Knight','Queen','King']]
DECKS = {'Full Deck':MAJORS+MINORS,'Major Arcana':MAJORS,'Minor Arcana':MINORS}

def new_session(question, kind, count, reversals=False, random_pile=True):
    cards = DECKS[kind].copy()
    for i in range(len(cards)-1,0,-1):
        j=secrets.randbelow(i+1)
        cards[i],cards[j]=cards[j],cards[i]
    n=len(cards); m=max(6,count)
    if count<1 or 3*m>n: raise ValueError('Too many main cards for this deck.')
    a,b=secrets.choice([(a,b) for a in range(m,n-2*m+1) for b in range(a+m,n-m+1)])
    piles=[cards[:a],cards[a:b],cards[b:]]
    s=dict(id=str(uuid4()),created_utc=datetime.now(timezone.utc).isoformat(),deck=kind,reversals=reversals,piles=piles,pile_sizes=list(map(len,piles)),selected_pile=None,used_piles=[],remaining=[],questions=[],log=[],closed=False)
    add_question(s,question,count,initial=True)
    if random_pile: select_pile(s,secrets.randbelow(3))
    return s

def select_pile(s,i):
    if s['closed'] or s['selected_pile'] is not None or not 0<=i<3: raise ValueError('Cannot select this pile.')
    s['selected_pile']=i+1; s['used_piles']=[i+1]; s['remaining']=s['piles'][i].copy()
    s['log'].append(dict(action='select_pile',pile=i+1))

def pending(s): return sum(q['count']-len(q['cards']) for q in s['questions'])

def add_other_piles(s):
    if s['closed'] or s['selected_pile'] is None: raise ValueError('No active session.')
    unused=[i for i in range(1,4) if i not in s['used_piles']]
    for i in unused: s['remaining'].extend(s['piles'][i-1])
    s['used_piles'].extend(unused); s['log'].append(dict(action='add_piles',piles=unused))

def add_question(s,question,count,parent=None,initial=False):
    if s['closed'] or count<1: raise ValueError('Enter a valid card count.')
    if not initial and (s['selected_pile'] is None or pending(s) or count>len(s['remaining'])): raise ValueError('Finish pending cards and check the available cards.')
    s['questions'].append(dict(id=len(s['questions'])+1,question=question.strip(),count=count,parent=parent,cards=[]))

def draw(s):
    if s['closed'] or s['selected_pile'] is None or not s['remaining']: raise ValueError('No cards available.')
    return dict(card=s['remaining'].pop(0),orientation='Reversed' if s['reversals'] and secrets.randbelow(2) else 'Upright')

def draw_main(s,qid):
    q=s['questions'][qid-1]
    if len(q['cards'])>=q['count']: raise ValueError('All main cards have been revealed.')
    c=draw(s); c['clarifiers']=[]; q['cards'].append(c)
    s['log'].append(dict(action='main',question_id=qid,position=len(q['cards']),card=c['card'],orientation=c['orientation']))
    return c

def clarify(s,qid,pos,question=''):
    q=s['questions'][qid-1]
    if not 1<=pos<=len(q['cards']): raise ValueError('Select a revealed card.')
    if len(s['remaining'])<=pending(s): raise ValueError('Reserve the pending main cards.')
    c=draw(s)
    if question.strip(): c['question']=question.strip()
    q['cards'][pos-1]['clarifiers'].append(c)
    s['log'].append(dict(action='clarifier',question_id=qid,position=pos,**c))
    return c

def secure_shuffle(cards):
    cards = cards[:]
    for i in range(len(cards)-1, 0, -1):
        j = secrets.randbelow(i+1)
        cards[i], cards[j] = cards[j], cards[i]
    return cards


def quick_reading(kind, count, clarifiers):
    """The supplied script's sequential cut and second shuffle, with a variable spread."""
    if count < 1 or clarifiers < 0:
        raise ValueError('Invalid spread size.')
    cards = secure_shuffle(DECKS[kind])
    n = len(cards)
    m = max(6, count * (1 + clarifiers))
    if n < 3*m:
        raise ValueError('Not enough cards for three eligible piles.')
    cut1 = secrets.randbelow(n - 3*m + 1) + m
    cut2 = secrets.randbelow(n - cut1 - 2*m + 1) + m
    piles = [cards[:cut1], cards[cut1:cut1+cut2], cards[cut1+cut2:]]
    s = dict(id=str(uuid4()), created_utc=datetime.now(timezone.utc).isoformat(),
             deck=kind, reversals=False, piles=piles, pile_sizes=list(map(len,piles)),
             selected_pile=None, used_piles=[], remaining=[], questions=[], log=[],
             closed=False, mode='quick', clarifiers_per_card=clarifiers)
    add_question(s, '', count, initial=True)
    select_pile(s, secrets.randbelow(3))
    # The original script reshuffles the selected pile and pops from its end.
    # The existing draw() pops from the front, so reverse to match that order.
    s['remaining'] = secure_shuffle(s['remaining'])[::-1]
    s['log'].append(dict(action='reshuffle_selected_pile', pile=s['selected_pile']))
    for pos in range(1, count+1):
        draw_main(s, 1)
        for _ in range(clarifiers):
            clarify(s, 1, pos)
    return s


def question_title(q):
    return q['question'].strip()


def export_session(s):
    result=deepcopy({k:v for k,v in s.items() if k not in ('piles','remaining')})
    result['cards_remaining']=len(s['remaining'])
    result['engine']='Python secrets + Fisher-Yates; draws without replacement'
    if s.get('mode') == 'quick':
        result['engine'] += '; sequential three-pile cut; selected pile reshuffled'
    result['reading_instructions']='Interpret only the drawn cards. Read main cards and their clarifiers together, integrate related questions, consider Rider-Waite imagery, symbolism and tensions. Do not invent cards or claim to know private thoughts or predict actual outcomes.'
    return result

# Streamlit interface
import streamlit as st
st.set_page_config(page_title='Tarot o’ Mine',page_icon='✦',layout='centered')
from pathlib import Path
import base64

visuals = Path(__file__).parent / 'visuals'
theme = (visuals / 'theme.css').read_text(encoding='utf-8')
skull = base64.b64encode((visuals / 'skull-medallion.webp').read_bytes()).decode('ascii')
banner = base64.b64encode((visuals / 'quick-banner.webp').read_bytes()).decode('ascii')
st.markdown(
    f'<style>{theme}:root{{--skull:url("data:image/webp;base64,{skull}");'
    f'--quick-banner:url("data:image/webp;base64,{banner}");}}</style>',
    unsafe_allow_html=True,
)
with st.container(key='tarot_brand'):
    st.title('Tarot o’ Mine', anchor=False)
    st.caption('Your questions. Your cards. Your intuition.')
if 'reading' not in st.session_state: st.session_state.reading=None
if 'history' not in st.session_state: st.session_state.history=[]

def action(fn,*args):
    try: fn(*args)
    except ValueError as e: st.error(str(e))
    else: st.rerun()

def name(c): return c['card']+(' · Reversed' if c['orientation']=='Reversed' else '')


# The card names are mapped to one verified, consistent historical deck.
from hashlib import md5
from urllib.parse import quote
from html import escape

CARD_FILES = {card: f"RWS Tarot {i:02d} {card.removeprefix('The ')}.jpg" for i, card in enumerate(MAJORS)}
for suit, prefix in [('Wands','Wands'),('Cups','Cups'),('Swords','Swords'),('Pentacles','Pents')]:
    for i, rank in enumerate(['Ace', *map(str, range(2,11)), 'Page','Knight','Queen','King'], 1):
        CARD_FILES[f'{rank} of {suit}'] = f'{prefix}{i:02d}.jpg'

def artwork_url(card_name):
    filename = CARD_FILES[card_name].replace(' ', '_')
    digest = md5(filename.encode('utf-8')).hexdigest()
    return f'https://upload.wikimedia.org/wikipedia/commons/{digest[0]}/{digest[:2]}/{quote(filename)}'

def tile(card, role):
    title = escape(card['card'])
    url = escape(artwork_url(card['card']), quote=True)
    reverse = card['orientation'] == 'Reversed'
    orientation = 'Reversed' if reverse else 'Upright'
    rotation = ' reversed' if reverse else ''
    note = escape(card.get('question', ''))
    # A tap opens the original scan; the preview itself respects orientation.
    return (f'<div class="tarot-tile"><div class="tarot-role">{escape(role)}</div>'
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" title="Open full-size artwork">'
            f'<img class="tarot-face{rotation}" src="{url}" alt="{title}" loading="lazy" referrerpolicy="no-referrer"></a>'
            f'<div class="tarot-title">{title}</div><div class="tarot-note">{orientation}</div>'
            f'<div class="tarot-note">{note}</div></div>')

def show_group(card, pos):
    tiles = [tile(card, f'Main card {pos}')]
    tiles += [tile(cl, f'Clarifier {j}') for j, cl in enumerate(card['clarifiers'], 1)]
    st.markdown('<div class="tarot-spread">' + ''.join(tiles) + '</div>', unsafe_allow_html=True)

def show_backs(count, start):
    tiles = [f'<div class="tarot-tile"><div class="tarot-role">Main card {i}</div><div class="tarot-back" aria-label="Face-down card">✦</div><div class="tarot-note">Unrevealed</div></div>' for i in range(start, start+count)]
    if tiles:
        st.markdown('<div class="tarot-spread">' + ''.join(tiles) + '</div>', unsafe_allow_html=True)

def start_quick(kind, count, clarifiers):
    try:
        fresh = quick_reading(kind, count, clarifiers)
    except ValueError as e:
        st.error(str(e))
        return
    previous = st.session_state.reading
    if previous is not None and not previous['closed'] and any(q['cards'] for q in previous['questions']):
        previous['closed'] = True
        st.session_state.history.append(export_session(previous))
    st.session_state.reading = fresh
    st.rerun()


with st.container(key='quick_reading'):
    st.subheader('Quick Reading', anchor=False)
    st.caption('One tap · No question required · Upright cards')
    with st.container(key='quick_choices'):
        if st.button('Major Arcana · 3 + 3', key='quick_major', type='primary', use_container_width=True):
            start_quick('Major Arcana', 3, 1)
        if st.button('Full Deck · 3 + 3', key='quick_full', type='primary', use_container_width=True):
            start_quick('Full Deck', 3, 1)
        if st.button('Full Deck · 5 + 10', key='quick_five', type='primary', use_container_width=True):
            start_quick('Full Deck', 5, 2)
    st.caption('Each tap starts a fresh deck. Previous revealed readings are saved in this visit’s history.')
    st.divider()

s=st.session_state.reading
if s is None:
    st.subheader('Interactive Reading')
    question=st.text_area('Your question (optional)',placeholder='What would you like to explore?')
    kind=st.radio('Deck',list(DECKS),horizontal=True)
    count=st.slider('Main cards',1,min(10,len(DECKS[kind])//3),3)
    rev=st.checkbox('Include reversed cards')
    mode=st.radio('Pile selection',['Random','Manual'],horizontal=True)
    if st.button('Shuffle & Cut',type='primary',use_container_width=True):
        try: st.session_state.reading=new_session(question,kind,count,rev,mode=='Random')
        except ValueError as e: st.error(str(e))
        else: st.rerun()
elif s['selected_pile'] is None:
    st.subheader('Choose a pile')
    for i,n in enumerate(s['pile_sizes']):
        if st.button(f'▥ Pile {i+1} · {n} cards',key=f'pile{i}',use_container_width=True): action(select_pile,s,i)
elif s.get('mode') == 'quick':
    st.caption(f"{s['deck']} · Pile {s['selected_pile']} · {s['pile_sizes'][s['selected_pile']-1]} cards in selected pile")
    for q in s['questions']:
        for pos,c in enumerate(q['cards'], 1):
            with st.container(border=True):
                show_group(c, pos)
elif st.toggle('Reading view · Cards only', key=f"reading_view_{s['id']}"):
    st.caption(f"{s['deck']} · Pile {s['selected_pile']} · {s['pile_sizes'][s['selected_pile']-1]} cards in selected pile")
    for q in s['questions']:
        st.divider()
        if question_title(q):
            st.subheader(question_title(q))
        if q['parent']: st.caption(f"Follow-up to question {q['parent']}")
        for pos,c in enumerate(q['cards'], 1):
            with st.container(border=True):
                show_group(c, pos)
        show_backs(q['count']-len(q['cards']), len(q['cards'])+1)
else:
    a,b=st.columns(2); a.metric('Cards available',len(s['remaining'])); b.metric('Cards drawn',sum(x['action'] in ('main','clarifier') for x in s['log']))
    st.caption(f"Selected pile: {s['selected_pile']} · {'Closed' if s['closed'] else 'Open session'}")
    if not s['closed'] and len(s['used_piles'])<3:
        with st.expander('Need more cards?'):
            st.caption('Add unused piles without reshuffling or repeating cards.')
            if st.button('Add remaining piles'): action(add_other_piles,s)
    for q in s['questions']:
        qid=q['id']; st.divider()
        if question_title(q):
            st.subheader(question_title(q))
        if q['parent']: st.caption(f"Follow-up to question {q['parent']}")
        left=q['count']-len(q['cards'])
        if left and not s['closed']:
            a,b=st.columns(2)
            if a.button(f"Reveal card {len(q['cards'])+1}",key=f'main{qid}',disabled=not s['remaining'],type='primary'): action(draw_main,s,qid)
            if b.button(f'Reveal all {left}',key=f'all{qid}',disabled=len(s['remaining'])<left):
                for _ in range(left): draw_main(s,qid)
                st.rerun()
        for pos,c in enumerate(q['cards'],1):
            with st.container(border=True):
                show_group(c, pos)
                if not s['closed']:
                    note=st.text_input('Clarifier question (optional)',key=f"note{qid}-{pos}-{len(c['clarifiers'])}")
                    if st.button('+ Add clarifier',key=f'clar{qid}-{pos}',disabled=len(s['remaining'])<=pending(s),use_container_width=True): action(clarify,s,qid,pos,note)
        show_backs(left, len(q['cards'])+1)
    if not s['closed'] and s['remaining'] and not pending(s):
        with st.expander('+ Ask a follow-up question'):
            with st.form('followup',clear_on_submit=True):
                parent=st.selectbox('Related to',[q['id'] for q in s['questions']],format_func=lambda i:question_title(s['questions'][i-1]) or f"Spread {i}")
                question=st.text_area('Follow-up question (optional)')
                count=st.number_input('Main cards',1,min(10,len(s['remaining'])),min(3,len(s['remaining'])),step=1)
                if st.form_submit_button('Add question'): action(add_question,s,question,count,parent)
if s is not None and s['selected_pile'] is not None:
    st.divider()
    if s.get('mode') != 'quick' and not s['closed']:
        with st.expander('Add a question or topic (optional)'):
            with st.form(f"topic_{s['id']}"):
                topic = st.text_input('Your question', value=s['questions'][0]['question'])
                if st.form_submit_button('Save topic'):
                    s['questions'][0]['question'] = topic.strip()
                    st.rerun()
    data=json.dumps(export_session(s),indent=2,ensure_ascii=False)
    st.download_button('Download session JSON',data,file_name=f"tarot_{s['id'][:8]}.json",mime='application/json',use_container_width=True)
    with st.expander('Copy session for ChatGPT'):
        st.caption('Copy this JSON and paste it into ChatGPT for a symbolic reading.')
        st.code(data,language='json')
    if not s['closed']:
        if st.button('Close session',use_container_width=True):
            s['closed']=True; st.session_state.history.append(export_session(s)); st.rerun()
    elif st.button('Start a new session',type='primary',use_container_width=True):
        st.session_state.reading=None; st.rerun()
if st.session_state.history:
    with st.expander('History for this visit'):
        for h in reversed(st.session_state.history):
            st.download_button(' · '.join(filter(None, (question_title(h['questions'][0]), h['created_utc'][:16].replace('T',' ')))),json.dumps(h,indent=2,ensure_ascii=False),file_name=f"tarot_{h['id'][:8]}.json",mime='application/json',key=f"hist{h['id']}")
st.caption('Python secrets · Fisher–Yates · No AI in card selection. Readings are symbolic. Session history is temporary; export before leaving.')

st.caption("Card artwork: Pamela Colman Smith, Rider–Waite–Smith (1909–1910), [Wikimedia Commons · historical scans](https://commons.wikimedia.org/wiki/Category:Rider-Waite-Smith_tarot_deck_(TaionWC)). Tap a card to view its original scan.")
