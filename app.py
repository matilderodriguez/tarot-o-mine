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
    if not question.strip(): raise ValueError('Enter a question first.')
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
    if s['closed'] or not question.strip() or count<1: raise ValueError('Enter a valid question.')
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

def export_session(s):
    result=deepcopy({k:v for k,v in s.items() if k not in ('piles','remaining')})
    result['cards_remaining']=len(s['remaining'])
    result['engine']='Python secrets + Fisher-Yates; draws without replacement'
    result['reading_instructions']='Interpret only the drawn cards. Read main cards and their clarifiers together, integrate related questions, consider Rider-Waite imagery, symbolism and tensions. Do not invent cards or claim to know private thoughts or predict actual outcomes.'
    return result

# Streamlit interface
import streamlit as st
st.set_page_config(page_title='Tarot o’ Mine',page_icon='✦',layout='centered')
st.markdown('''<style>.stApp {background:#151722;color:#f4eee2} .block-container{max-width:780px;padding-top:2rem} h1,h2,h3{color:#e6c78d!important} [data-testid="stButton"] button{border-radius:12px}</style>''',unsafe_allow_html=True)
st.title('✦ Tarot o’ Mine')
st.caption('Your questions. Your cards. Your intuition.')
if 'reading' not in st.session_state: st.session_state.reading=None
if 'history' not in st.session_state: st.session_state.history=[]

def action(fn,*args):
    try: fn(*args)
    except ValueError as e: st.error(str(e))
    else: st.rerun()

def name(c): return c['card']+(' · Reversed' if c['orientation']=='Reversed' else '')

s=st.session_state.reading
if s is None:
    st.subheader('New reading')
    question=st.text_area('Your question',placeholder='What would you like to explore?')
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
else:
    a,b=st.columns(2); a.metric('Cards available',len(s['remaining'])); b.metric('Cards drawn',sum(x['action'] in ('main','clarifier') for x in s['log']))
    st.caption(f"Selected pile: {s['selected_pile']} · {'Closed' if s['closed'] else 'Open session'}")
    if not s['closed'] and len(s['used_piles'])<3:
        with st.expander('Need more cards?'):
            st.caption('Add unused piles without reshuffling or repeating cards.')
            if st.button('Add remaining piles'): action(add_other_piles,s)
    for q in s['questions']:
        qid=q['id']; st.divider(); st.subheader(f"{qid}. {q['question']}")
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
                st.caption(f'Main card {pos}'); st.markdown(f"### {name(c)}")
                for j,cl in enumerate(c['clarifiers'],1):
                    st.markdown(f'**Clarifier {j}:** {name(cl)}')
                    if cl.get('question'): st.caption(cl['question'])
                if not s['closed']:
                    note=st.text_input('Clarifier question (optional)',key=f"note{qid}-{pos}-{len(c['clarifiers'])}")
                    if st.button('+ Add clarifier',key=f'clar{qid}-{pos}',disabled=len(s['remaining'])<=pending(s),use_container_width=True): action(clarify,s,qid,pos,note)
    if not s['closed'] and s['remaining'] and not pending(s):
        with st.expander('+ Ask a follow-up question'):
            with st.form('followup',clear_on_submit=True):
                parent=st.selectbox('Related to',[q['id'] for q in s['questions']],format_func=lambda i:f"{i}. {s['questions'][i-1]['question']}")
                question=st.text_area('Follow-up question')
                count=st.number_input('Main cards',1,min(10,len(s['remaining'])),min(3,len(s['remaining'])),step=1)
                if st.form_submit_button('Add question'): action(add_question,s,question,count,parent)
    st.divider()
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
            st.download_button(h['questions'][0]['question'],json.dumps(h,indent=2,ensure_ascii=False),file_name=f"tarot_{h['id'][:8]}.json",mime='application/json',key=f"hist{h['id']}")
st.caption('Python secrets · Fisher–Yates · No AI in card selection. Readings are symbolic. Session history is temporary; export before leaving.')
