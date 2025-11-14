"""
Módulo de Pré-processamento de Imagens para OCR - Versão Moderna
Baseado nas melhores práticas de sistemas comerciais (Google Vision, Azure, Mistral)
Abordagem conservadora: melhor processar menos do que destruir informações
"""

import cv2
import numpy as np
from PIL import Image
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """Pipeline moderno de pré-processamento - conservador e adaptativo"""
    
    def __init__(self):
        self.target_dpi = 300
        
    def preprocess(self, image, apply_all=True, **kwargs):
        """
        Aplica pipeline CONSERVADOR de pré-processamento
        
        Filosofia: Menos é mais. Melhor uma imagem levemente melhorada 
        do que uma imagem destruída por processamento excessivo.
        
        Args:
            image: imagem PIL ou numpy array
            apply_all: se True, aplica pipeline básico (recomendado)
            **kwargs: configurações específicas
        
        Returns:
            tuple: (imagem_preprocessada, metadata)
        """
        metadata = {
            "etapas_aplicadas": [],
            "original_shape": None,
            "final_shape": None,
            "quality_score": 0
        }
        
        # Converter PIL para OpenCV se necessário
        if isinstance(image, Image.Image):
            img = np.array(image)
            if len(img.shape) == 3:
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        else:
            img = image.copy()
        
        metadata["original_shape"] = img.shape
        
        try:
            # Avaliar qualidade da imagem inicial
            quality = self._assess_image_quality(img)
            metadata["quality_score"] = quality
            logger.info(f"Qualidade da imagem: {quality:.2f}/100")
            
            # 1. Conversão para escala de cinza (sempre)
            if len(img.shape) == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                metadata["etapas_aplicadas"].append("grayscale")
            
            # 2. Normalização de resolução (sempre fazer primeiro)
            if apply_all or kwargs.get("apply_resize", True):
                img = self._smart_resize(img)
                metadata["etapas_aplicadas"].append("smart_resize")
            
            # 3. Correção de orientação - APENAS se explicitamente solicitado
            # NÃO aplicar por padrão no apply_all
            if kwargs.get("apply_deskew", False):
                img, angle = self._correct_orientation(img)
                if abs(angle) > 0.5:
                    metadata["etapas_aplicadas"].append(f"orientation({angle:.0f}°)")
            
            # 4. CLAHE SUAVE (apenas se imagem escura)
            if (apply_all or kwargs.get("apply_clahe", True)) and quality < 60:
                img = self._gentle_clahe(img)
                metadata["etapas_aplicadas"].append("gentle_clahe")
            
            # 5. Remoção de ruído LEVE (apenas se necessário)
            if kwargs.get("apply_denoise", False) and quality < 50:
                img = self._gentle_denoise(img)
                metadata["etapas_aplicadas"].append("gentle_denoise")
            
            # 6. NÃO fazer crop automático por padrão (muito arriscado)
            # Apenas se explicitamente solicitado
            if kwargs.get("apply_autocrop", False):
                img = self._conservative_crop(img)
                metadata["etapas_aplicadas"].append("conservative_crop")
            
            # 7. Sharpening SUAVE (apenas se imagem desfocada)
            if (apply_all or kwargs.get("apply_sharpen", False)) and quality < 55:
                img = self._gentle_sharpen(img)
                metadata["etapas_aplicadas"].append("gentle_sharpen")
            
            # 8. NÃO aplicar binarização por padrão (destrutivo para fotos)
            # Apenas se explicitamente solicitado E imagem for scan B&W
            if kwargs.get("apply_binarization", False):
                # Verificar se a imagem beneficiaria de binarização
                if self._should_binarize(img):
                    img = self._gentle_threshold(img)
                    metadata["etapas_aplicadas"].append("gentle_threshold")
                else:
                    logger.info("Binarização pulada - imagem não se beneficiaria")
            
            metadata["final_shape"] = img.shape
            logger.info(f"Pré-processamento concluído: {len(metadata['etapas_aplicadas'])} etapas")
            
            return img, metadata
            
        except Exception as e:
            logger.error(f"Erro no pré-processamento: {e}")
            return img, metadata
    
    def _assess_image_quality(self, img):
        """Avalia qualidade da imagem (0-100)"""
        try:
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()
            
            # Verificar nitidez usando Laplaciano
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Verificar contraste
            contrast = gray.std()
            
            # Verificar brilho médio
            brightness = gray.mean()
            
            # Score combinado
            sharpness_score = min(100, laplacian_var / 10)
            contrast_score = min(100, contrast / 2)
            brightness_score = 100 - abs(brightness - 128) / 1.28
            
            quality = (sharpness_score + contrast_score + brightness_score) / 3
            return quality
            
        except:
            return 50  # Qualidade média se falhar
    
    def _smart_resize(self, img):
        """Resize inteligente baseado em conteúdo"""
        height, width = img.shape[:2]
        
        # Se muito pequena, aumentar com interpolação cúbica
        if width < 1500:
            scale = 1800 / width
            new_width = int(width * scale)
            new_height = int(height * scale)
            img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            logger.info(f"Imagem aumentada: {width}x{height} -> {new_width}x{new_height}")
        
        # Se muito grande, reduzir suavemente
        elif width > 3500:
            scale = 3000 / width
            new_width = int(width * scale)
            new_height = int(height * scale)
            img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
            logger.info(f"Imagem reduzida: {width}x{height} -> {new_width}x{new_height}")
        
        return img
    
    def detectar_orientacao(self, imagem):
        """
        Detecta a orientação correta da imagem usando OCR
        Retorna o ângulo necessário para corrigir (0, 90, 180, 270)
        """
        # Converte para RGB se necessário
        if len(imagem.shape) == 2:
            img_rgb = cv2.cvtColor(imagem, cv2.COLOR_GRAY2RGB)
        else:
            img_rgb = imagem.copy()
        
        melhor_confianca = -1
        melhor_rotacao = 0
        
        # Testa cada orientação possível
        for angulo in [0, 90, 180, 270]:
            # Rotaciona a imagem
            if angulo == 90:
                img_rotacionada = cv2.rotate(img_rgb, cv2.ROTATE_90_CLOCKWISE)
            elif angulo == 180:
                img_rotacionada = cv2.rotate(img_rgb, cv2.ROTATE_180)
            elif angulo == 270:
                img_rotacionada = cv2.rotate(img_rgb, cv2.ROTATE_90_COUNTERCLOCKWISE)
            else:
                img_rotacionada = img_rgb
            
            # Converte para PIL Image
            img_pil = Image.fromarray(img_rotacionada)
            
            # Usa Tesseract para detectar orientação e obter confiança
            try:
                import pytesseract
                import time
                
                # Timeout simples: se demorar mais que 5 segundos, pula
                start_time = time.time()
                osd = pytesseract.image_to_osd(img_pil)
                
                if time.time() - start_time > 5:
                    logger.warning(f"   Tesseract lento na rotação {angulo}°, pulando...")
                    continue
                
                # Extrai a confiança do resultado
                for linha in osd.split('\n'):
                    if 'Orientation confidence' in linha or 'Script confidence' in linha:
                        confianca = float(linha.split(':')[1].strip())
                        
                        if confianca > melhor_confianca:
                            melhor_confianca = confianca
                            melhor_rotacao = angulo
                        break
            except Exception as e:
                logger.warning(f"   Erro na rotação {angulo}°: {e}")
                continue
        
        return melhor_rotacao

    def detectar_orientacao_simples(self, imagem):
        """
        Método alternativo mais rápido usando análise de gradientes
        Útil quando não há texto claro ou OCR não está disponível
        """
        gray = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY) if len(imagem.shape) == 3 else imagem
        
        # Detecta bordas
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Detecta linhas usando Hough Transform
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
        
        if lines is None:
            return 0
        
        # Analisa os ângulos das linhas
        angulos = []
        for line in lines:
            rho, theta = line[0]
            angulo = np.degrees(theta)
            angulos.append(angulo)
        
        # Determina a orientação predominante
        angulos = np.array(angulos)
        
        # Agrupa ângulos em bins de 90 graus
        hist, bins = np.histogram(angulos, bins=[0, 45, 135, 180])
        
        # Se a maioria das linhas está vertical (90 graus)
        if hist[1] > hist[0] and hist[1] > hist[2]:
            return 90
        
        return 0

    def corrigir_inclinacao_deskew(self, imagem):
        """
        Corrige pequenas inclinações (skew) da imagem
        """
        gray = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY) if len(imagem.shape) == 3 else imagem
        
        # Binarização
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        
        # Detecta coordenadas dos pixels de texto
        coords = np.column_stack(np.where(thresh > 0))
        
        # Calcula o ângulo de inclinação
        angle = cv2.minAreaRect(coords)[-1]
        
        # Ajusta o ângulo
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        # Rotaciona a imagem para corrigir
        (h, w) = imagem.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotacionada = cv2.warpAffine(imagem, M, (w, h), 
                                      flags=cv2.INTER_CUBIC, 
                                      borderMode=cv2.BORDER_REPLICATE)
        
        return rotacionada, angle

    def _detect_orientation(self, img):
        """
        Detecta a orientação do documento (0°, 90°, 180°, 270°)
        Retorna o ângulo de rotação necessário para corrigir
        
        Método robusto baseado em análise de texto e layout
        """
        try:
            # MÉTODO 1: Tesseract OSD (mais confiável quando disponível)
            try:
                import pytesseract
                
                # Aumentar o tamanho da imagem para melhorar a detecção
                h, w = img.shape[:2]
                if w < 1000:
                    scale = 1500 / w
                    img_scaled = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                else:
                    img_scaled = img
                
                # Tentar detectar orientação com Tesseract
                osd_result = pytesseract.image_to_osd(img_scaled, output_type=pytesseract.Output.DICT)
                rotation_angle = osd_result.get('rotate', 0)
                confidence = osd_result.get('orientation_conf', 0)
                
                logger.info(f"Tesseract OSD detectou: {rotation_angle}° (confiança: {confidence:.1f}%)")
                
                # Se confiança > 1.0, usar a rotação detectada
                if confidence > 1.0:
                    # Converter para o sistema de rotação do cv2.rotate
                    if rotation_angle == 0:
                        return 0
                    elif rotation_angle == 90:
                        return 270  # Rotacionar 270° no sentido horário = -90°
                    elif rotation_angle == 180:
                        return 180
                    elif rotation_angle == 270:
                        return 90  # Rotacionar 90° no sentido horário
                
            except Exception as e:
                logger.debug(f"Tesseract OSD não disponível: {e}")
            
            # MÉTODO 2: Análise de layout e distribuição de texto
            height, width = img.shape[:2]
            orientations = [0, 90, 180, 270]
            scores = []
            
            for angle in orientations:
                rotated = self._rotate_image(img, angle)
                score = self._score_orientation(rotated)
                scores.append(score)
                logger.debug(f"Orientação {angle}°: score={score:.2f}")
            
            # A orientação correta tem o MAIOR score
            best_idx = np.argmax(scores)
            best_angle = orientations[best_idx]
            
            logger.info(f"Orientação detectada: {best_angle}° (score: {scores[best_idx]:.2f})")
            return best_angle
            
        except Exception as e:
            logger.warning(f"Detecção de orientação falhou: {e}")
            return 0
    
    def _score_orientation(self, img):
        """
        Calcula um score para uma orientação específica
        Maior score = orientação mais provável de estar correta
        """
        try:
            h, w = img.shape[:2]
            
            # 1. Preferência por formato retrato (documentos geralmente são retrato)
            aspect_ratio = h / w
            aspect_score = 0
            if 1.3 < aspect_ratio < 1.6:  # Formato A4/carta
                aspect_score = 100
            elif aspect_ratio > 1.0:  # Retrato
                aspect_score = 50
            else:  # Paisagem
                aspect_score = 0
            
            # 2. Análise de linhas horizontais (texto tem linhas horizontais)
            # Aplicar detecção de bordas
            edges = cv2.Canny(img, 50, 150, apertureSize=3)
            
            # Detectar linhas com HoughLines
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, 
                                   minLineLength=w//4, maxLineGap=10)
            
            horizontal_lines = 0
            vertical_lines = 0
            
            if lines is not None:
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    angle = np.abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
                    
                    # Horizontal (0° ou 180°)
                    if angle < 15 or angle > 165:
                        horizontal_lines += 1
                    # Vertical (90°)
                    elif 75 < angle < 105:
                        vertical_lines += 1
            
            # Documentos têm mais linhas horizontais (texto)
            lines_score = horizontal_lines * 2  # Preferir horizontal
            
            # 3. Análise de distribuição de pixels (texto tem padrão específico)
            # Projeção horizontal (soma de pixels em cada linha)
            h_projection = np.sum(img < 200, axis=1)  # Pixels escuros
            v_projection = np.sum(img < 200, axis=0)
            
            # Variância na projeção horizontal (texto cria picos e vales)
            h_variance = np.var(h_projection)
            v_variance = np.var(v_projection)
            
            # Texto em orientação correta tem maior variância horizontal
            projection_score = h_variance / (v_variance + 1)
            
            # Score final combinado
            total_score = (aspect_score * 0.4 + 
                          lines_score * 0.3 + 
                          projection_score * 0.3)
            
            return total_score
            
        except Exception as e:
            logger.warning(f"Erro ao calcular score de orientação: {e}")
            return 0
    
    def _rotate_image(self, img, angle):
        """Rotaciona imagem por 0, 90, 180 ou 270 graus"""
        if angle == 0:
            return img
        elif angle == 90:
            return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        elif angle == 180:
            return cv2.rotate(img, cv2.ROTATE_180)
        elif angle == 270:
            return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        else:
            # Para ângulos arbitrários
            (h, w) = img.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            return cv2.warpAffine(img, M, (w, h), 
                                borderMode=cv2.BORDER_CONSTANT,
                                borderValue=255)
    
    def _correct_orientation(self, img):
        """
        Correção de orientação do documento com deskew avançado
        Aplica detecção de orientação + correção de inclinação
        """
        try:
            logger.info("=" * 60)
            logger.info("DETECÇÃO E CORREÇÃO DE ORIENTAÇÃO DO DOCUMENTO")
            logger.info("=" * 60)
            
            # 1. Detectar orientação principal (0°, 90°, 180°, 270°)
            logger.info("1. Detectando orientação principal...")
            try:
                angulo_orientacao = self.detectar_orientacao(img)
                logger.info(f"   Orientação detectada com OCR: {angulo_orientacao}°")
            except:
                logger.info("   OCR falhou, usando método alternativo...")
                angulo_orientacao = self.detectar_orientacao_simples(img)
                logger.info(f"   Orientação detectada com gradientes: {angulo_orientacao}°")
            
            # 2. Aplicar rotação principal se necessário
            if angulo_orientacao != 0:
                logger.info(f"2. Aplicando rotação principal: {angulo_orientacao}°")
                if angulo_orientacao == 90:
                    img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
                elif angulo_orientacao == 180:
                    img = cv2.rotate(img, cv2.ROTATE_180)
                elif angulo_orientacao == 270:
                    img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
                logger.info("   ✓ Rotação principal aplicada")
            else:
                logger.info("2. ✓ Documento já está na orientação correta")
            
            # 3. Garantir modo retrato (altura > largura)
            h, w = img.shape[:2]
            if w > h:
                logger.info("3. Convertendo para modo retrato...")
                img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
                logger.info("   ✓ Convertido para retrato")
            else:
                logger.info("3. ✓ Já está em modo retrato")
            
            # 4. Corrigir inclinações pequenas (deskew)
            logger.info("4. Corrigindo inclinação fina (deskew)...")
            try:
                img_final, angulo_deskew = self.corrigir_inclinacao_deskew(img)
                if abs(angulo_deskew) > 0.5:
                    logger.info(f"   ✓ Inclinação corrigida: {angulo_deskew:.2f}°")
                else:
                    logger.info("   ✓ Nenhuma inclinação significativa detectada")
                    img_final = img
            except Exception as e:
                logger.warning(f"   ⚠️ Deskew falhou: {e}")
                img_final = img
                angulo_deskew = 0
            
            logger.info("=" * 60)
            logger.info("✓ CORREÇÃO DE ORIENTAÇÃO CONCLUÍDA")
            logger.info(f"  - Rotação principal: {angulo_orientacao}°")
            logger.info(f"  - Correção de inclinação: {angulo_deskew:.2f}°")
            logger.info("=" * 60)
            
            return img_final, angulo_orientacao + angulo_deskew
            
        except Exception as e:
            logger.warning(f"Correção de orientação falhou: {e}")
            import traceback
            traceback.print_exc()
            return img, 0.0
    
    def _gentle_clahe(self, img):
        """CLAHE SUAVE - não exagerar no contraste"""
        # Valores conservadores
        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
        return clahe.apply(img)
    
    def _gentle_denoise(self, img):
        """Remoção de ruído LEVE - preservar detalhes"""
        # Parâmetros suaves
        return cv2.fastNlMeansDenoising(img, None, h=7, templateWindowSize=7, searchWindowSize=21)
    
    def _gentle_sharpen(self, img):
        """Sharpening SUAVE para melhorar nitidez sem artefatos"""
        # Kernel suave de sharpening
        kernel = np.array([[-1,-1,-1],
                          [-1, 9,-1],
                          [-1,-1,-1]]) / 9
        
        sharpened = cv2.filter2D(img, -1, kernel)
        
        # Misturar com original (50/50) para não exagerar
        return cv2.addWeighted(img, 0.5, sharpened, 0.5, 0)
    
    def _conservative_crop(self, img):
        """Crop MUITO conservador - apenas bordas óbvias"""
        height, width = img.shape[:2]
        
        # Apenas remover bordas muito óbvias (mais de 95% brancas)
        margin = 10
        
        # Verificar linhas horizontais
        h_sums = np.sum(img > 240, axis=1)
        h_white = h_sums > (width * 0.95)
        
        # Verificar linhas verticais
        v_sums = np.sum(img > 240, axis=0)
        v_white = v_sums > (height * 0.95)
        
        # Encontrar primeira/última linha com conteúdo
        h_content = np.where(~h_white)[0]
        v_content = np.where(~v_white)[0]
        
        if len(h_content) == 0 or len(v_content) == 0:
            return img
        
        y1 = max(0, h_content[0] - margin)
        y2 = min(height, h_content[-1] + margin)
        x1 = max(0, v_content[0] - margin)
        x2 = min(width, v_content[-1] + margin)
        
        # Apenas fazer crop se remover no mínimo 5% da imagem
        new_area = (y2 - y1) * (x2 - x1)
        if new_area > height * width * 0.95:
            logger.info("Crop conservador: bordas insuficientes para remover")
            return img
        
        logger.info(f"Crop conservador aplicado: {width}x{height} -> {x2-x1}x{y2-y1}")
        return img[y1:y2, x1:x2]
    
    def _should_binarize(self, img):
        """Verifica se imagem se beneficiaria de binarização"""
        # Contar quantos valores únicos existem
        unique_values = len(np.unique(img))
        
        # Se já tem poucos valores, pode binarizar
        if unique_values < 50:
            return True
        
        # Verificar se é predominantemente B&W
        hist = cv2.calcHist([img], [0], None, [256], [0, 256])
        
        # Se picos nos extremos (0-50 e 200-255), é B&W
        dark_pixels = np.sum(hist[0:50])
        bright_pixels = np.sum(hist[200:256])
        total_pixels = img.shape[0] * img.shape[1]
        
        bw_ratio = (dark_pixels + bright_pixels) / total_pixels
        
        return bw_ratio > 0.7  # 70% dos pixels são B&W
    
    def _gentle_threshold(self, img):
        """Binarização SUAVE com threshold adaptativo"""
        # Usar método adaptativo com parâmetros conservadores
        binary = cv2.adaptiveThreshold(
            img, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=15,  # Maior = mais suave
            C=3  # Menor = menos agressivo
        )
        
        # Misturar com original (70% processado, 30% original)
        # Isso evita perda total de informação
        return cv2.addWeighted(binary, 0.7, img, 0.3, 0)
    
    def processar_documento_completo(self, caminho_imagem, usar_ocr=True):
        """
        Pipeline completo: detecta orientação + corrige inclinação
        Integrado com Mistral AI
        """
        # Carrega a imagem
        imagem = cv2.imread(caminho_imagem)
        
        if imagem is None:
            raise ValueError("Não foi possível carregar a imagem")
        
        logger.info("1. Imagem carregada")
        
        # Detecta e corrige orientação (0, 90, 180, 270 graus)
        if usar_ocr:
            logger.info("2. Detectando orientação com OCR...")
            try:
                # Timeout de 15 segundos para todo o processo de OCR
                import time
                start_time = time.time()
                angulo_orientacao = self.detectar_orientacao(imagem)
                
                if time.time() - start_time > 15:
                    logger.warning("   OCR demorou muito, usando método alternativo...")
                    angulo_orientacao = self.detectar_orientacao_simples(imagem)
                    
            except Exception as e:
                logger.warning(f"   OCR falhou ({e}), usando método alternativo...")
                angulo_orientacao = self.detectar_orientacao_simples(imagem)
        else:
            logger.info("2. Detectando orientação com análise de gradientes...")
            angulo_orientacao = self.detectar_orientacao_simples(imagem)
        
        logger.info(f"   Rotação necessária: {angulo_orientacao}°")
        
        # Aplica a rotação para orientação correta
        if angulo_orientacao == 90:
            imagem = cv2.rotate(imagem, cv2.ROTATE_90_CLOCKWISE)
        elif angulo_orientacao == 180:
            imagem = cv2.rotate(imagem, cv2.ROTATE_180)
        elif angulo_orientacao == 270:
            imagem = cv2.rotate(imagem, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        # Garante modo retrato (altura > largura)
        h, w = imagem.shape[:2]
        if w > h:
            logger.info("3. Convertendo para modo retrato...")
            imagem = cv2.rotate(imagem, cv2.ROTATE_90_CLOCKWISE)
        else:
            logger.info("3. Já está em modo retrato")
        
        # Corrige inclinações pequenas (deskew)
        logger.info("4. Corrigindo inclinação fina (deskew)...")
        try:
            imagem_final, angulo_deskew = self.corrigir_inclinacao_deskew(imagem)
            logger.info(f"   Inclinação corrigida: {angulo_deskew:.2f}°")
        except:
            logger.info("   Não foi possível fazer deskew, mantendo imagem atual")
            imagem_final = imagem
            angulo_deskew = 0
        
        return imagem_final, angulo_orientacao, angulo_deskew

    def preprocess_for_mistral(self, image_path):
        """
        Pré-processamento OTIMIZADO para Mistral Vision API
        
        Pipeline testado e aprovado:
        - Grayscale (conversão para escala de cinza)
        - Smart Resize (normalização de resolução)
        - CLAHE (equalização adaptativa de contraste)
        - Remoção de Ruído (filtro bilateral)
        - Sharpening (aumento de nitidez)
        """
        img = cv2.imread(image_path)
        
        if img is None:
            raise ValueError(f"Não foi possível carregar: {image_path}")
        
        # Pipeline OTIMIZADO baseado em testes reais
        processed, metadata = self.preprocess(
            img,
            apply_all=False,  # Aplicar apenas o necessário
            apply_resize=True,  # ✅ Smart resize
            apply_deskew=False,  # Deskew NÃO por padrão
            apply_clahe=True,  # ✅ CLAHE - equalização adaptativa
            apply_denoise=True,  # ✅ Remoção de ruído (bilateral)
            apply_autocrop=False,  # NUNCA para IA
            apply_sharpen=True,  # ✅ Sharpening - aumentar nitidez
            apply_binarization=False  # NUNCA para IA moderna
        )
        
        return processed, metadata


def aplicar_preprocessing_basico(image_path):
    """
    Função auxiliar - pré-processamento básico
    """
    preprocessor = ImagePreprocessor()
    return preprocessor.preprocess_for_mistral(image_path)


if __name__ == "__main__":
    print("=" * 70)
    print("🔬 Módulo de Pré-processamento OCR Moderno v3.0")
    print("=" * 70)
    print()
    print("✨ Filosofia: MENOS É MAIS")
    print("   - Pré-processamento conservador e inteligente")
    print("   - Preservação de informações > Transformações agressivas")
    print("   - Otimizado para APIs de IA moderna (Mistral, GPT-4V, etc)")
    print()
    print("📋 Pipeline Padrão (apply_all=True):")
    print("   1. ✅ Grayscale (sempre)")
    print("   2. ✅ Smart Resize (sempre)")
    print("   3. ⬜ Orientation Correction (apenas se apply_deskew=True)")
    print("   4. ✅ Gentle CLAHE (se qualidade <60)")
    print("   5. ⬜ Denoise (apenas se solicitado)")
    print("   6. ⬜ Auto Crop (apenas se solicitado)")
    print("   7. ⬜ Sharpen (apenas se solicitado)")
    print("   8. ⬜ Binarização (apenas se solicitado E adequado)")
    print()
    print("🎯 Uso Recomendado:")
    print("   preprocessor = ImagePreprocessor()")
    print("   img, meta = preprocessor.preprocess_for_mistral(path)")
    print()
    print("=" * 70)
