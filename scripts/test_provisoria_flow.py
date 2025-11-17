import sys
import time
import os
from typing import List

# Garantir que a raiz do projeto esteja no sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from automation.actions.provisoria_action import ProvisoriaAction


def _find_parecer_pf(driver) -> str | None:
    # tenta no contexto atual
    try:
        el = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#CHPF_PARECER, textarea#CHPF_PARECER"))
        )
        val = (el.get_attribute('value') or el.text or '').strip()
        if val:
            return val
    except Exception:
        pass
    # tenta em iframes
    try:
        iframes = driver.find_elements(By.CSS_SELECTOR, 'iframe')
        for f in iframes:
            try:
                driver.switch_to.frame(f)
                el = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#CHPF_PARECER, textarea#CHPF_PARECER"))
                )
                val = (el.get_attribute('value') or el.text or '').strip()
                driver.switch_to.default_content()
                if val:
                    return val
                driver.switch_to.default_content()
            except Exception:
                driver.switch_to.default_content()
                continue
    except Exception:
        pass
    return None


def main(codes: List[str]) -> int:
    print("[TEST] Iniciando ProvisoriaAction...")
    a = ProvisoriaAction()
    print("[TEST] Fazendo login...")
    if not a.login():
        print("[FAIL] Login falhou")
        return 1
    print("[OK] Login")
    try:
        a.driver.get('https://justica.servicos.gov.br/workspace')
    except Exception:
        pass

    rc = 0
    for code in codes:
        print("\n=== TESTE CÓDIGO:", code, '===')
        ok = a.aplicar_filtros(code)
        if not ok:
            print("[FAIL] aplicar_filtros falhou para", code)
            rc = 2
            continue
        # dar tempo para carregar
        time.sleep(2)
        try:
            # tentar assegurar data inicial
            if getattr(a, 'data_inicial_processo', None):
                print("[OK] Data inicial:", a.data_inicial_processo)
            else:
                print("[WARN] Data inicial não encontrada")
        except Exception:
            print("[WARN] Data inicial não disponível")
        # tentar encontrar parecer PF
        pf = _find_parecer_pf(a.driver)
        if pf is not None:
            print("[OK] CHPF_PARECER:", pf[:120].replace('\n',' ') + ("..." if len(pf) > 120 else ""))
        else:
            print("[WARN] Não encontrou CHPF_PARECER")
            rc = max(rc, 3)
        time.sleep(1)
    try:
        a.fechar()
    except Exception:
        pass
    return rc


if __name__ == '__main__':
    codes = sys.argv[1:] or ["743961"]
    exit(main(codes))
