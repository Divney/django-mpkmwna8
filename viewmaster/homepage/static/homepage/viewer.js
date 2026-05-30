(function () {
    const configEl = document.getElementById('viewmaster-config');
    if (!configEl) return;

    const CONFIG = JSON.parse(configEl.textContent);
    if (!CONFIG || typeof CONFIG !== 'object' || Array.isArray(CONFIG)) {
        console.error('ViewMaster: invalid viewer config');
        return;
    }

    const videoContainer = document.getElementById('video-container');
    const fullscreenButton = document.getElementById('fullscreen-button');
    const favoriteStar = document.getElementById('favorite-star');
    const staticImgBase = CONFIG.staticImgBase || '/static/homepage/img/';

    const videoCount = CONFIG.videoCount;
    const defaultStartIndex = Math.min(CONFIG.defaultStartIndex, Math.max(0, videoCount - 1));
    const mostSimilarOrder = CONFIG.mostSimilarOrder || [];
    const leastSimilarOrder = CONFIG.leastSimilarOrder || [];
    const similarityOrdersAvailable = CONFIG.similarityOrdersAvailable;
    const jumpToSimilarAvailable = CONFIG.jumpToSimilarAvailable;
    const topNeighbors = CONFIG.topNeighbors || [];

    let videoOrder = [];
    let selectedOrder = null;
    let similarLayout = null;
    let parentCatalogIndex = defaultStartIndex;
    let orderSelectionShown = false;
    let currentIndex = 0;
    let inputSequence = '';
    let inputTimeout;
    let gridTimeout;
    let indexDisplayTimeout;
    let gridVisible = false;
    let favorites = new Set(CONFIG.favoriteIndices || []);
    const urlCache = new Map();
    let activeVideo = null;

    fullscreenButton.style.backgroundImage = `url('${staticImgBase}arrows-alt_ffffff_64.png')`;

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    function apiVideoUrl(catalogIndex) {
        return CONFIG.apiVideoUrlTemplate.replace('{catalog_index}', String(catalogIndex));
    }

    async function fetchVideoUrl(catalogIndex, bustCache) {
        if (!bustCache && urlCache.has(catalogIndex)) {
            return urlCache.get(catalogIndex);
        }
        const response = await fetch(apiVideoUrl(catalogIndex), { credentials: 'same-origin' });
        if (!response.ok) {
            throw new Error(`Failed to load video URL (${response.status})`);
        }
        const data = await response.json();
        urlCache.set(catalogIndex, data.url);
        return data.url;
    }

    function prefetchAdjacentUrls() {
        if (videoOrder.length === 0) return;
        const prevIndex = getOriginalIndex((currentIndex - 1 + videoOrder.length) % videoOrder.length);
        const nextIndex = getOriginalIndex((currentIndex + 1) % videoOrder.length);
        fetchVideoUrl(prevIndex).catch(() => {});
        fetchVideoUrl(nextIndex).catch(() => {});
    }

    async function displayVideo(catalogIndex) {
        const video = document.createElement('video');
        video.autoplay = true;
        video.loop = true;
        video.muted = true;
        video.playsInline = true;
        video.style.position = 'fixed';
        video.style.top = '0';
        video.style.left = '0';
        video.style.zIndex = '1';
        video.style.width = '100vw';
        video.style.height = '100vh';
        video.style.objectFit = 'contain';

        videoContainer.innerHTML = '';
        videoContainer.appendChild(video);
        activeVideo = video;

        const loadWithUrl = async (bustCache) => {
            const url = await fetchVideoUrl(catalogIndex, bustCache);
            video.src = url;
            await video.play().catch(() => {});
        };

        video.addEventListener('error', () => {
            urlCache.delete(catalogIndex);
            loadWithUrl(true).catch((err) => console.error(err));
        });

        try {
            await loadWithUrl(false);
            prefetchAdjacentUrls();
        } catch (err) {
            console.error(err);
        }
    }

    function getOriginalIndex(orderIndex) {
        if (orderIndex < 0 || orderIndex >= videoOrder.length) {
            return 0;
        }
        return videoOrder[orderIndex];
    }

    function displayVideoByOrderIndex(orderIndex) {
        const originalIndex = getOriginalIndex(orderIndex);
        displayVideo(originalIndex);
        updateFavoriteStar();
    }

    function isCurrentVideoFavorited() {
        if (videoOrder.length === 0) return false;
        return favorites.has(getOriginalIndex(currentIndex));
    }

    async function toggleFavorite() {
        if (videoOrder.length === 0) return;
        const originalIndex = getOriginalIndex(currentIndex);
        const wasFavorited = favorites.has(originalIndex);
        const wasInFavoritesMode = selectedOrder === 'favorites';

        const response = await fetch(CONFIG.apiFavoritesToggle, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify({ catalog_index: originalIndex }),
        });

        if (!response.ok) {
            console.error('Failed to toggle favorite');
            return;
        }

        const data = await response.json();
        if (data.favorited) {
            favorites.add(originalIndex);
        } else {
            favorites.delete(originalIndex);
        }

        if (wasInFavoritesMode && wasFavorited) {
            videoOrder = buildFavoritesOrder();
            if (videoOrder.length === 0) {
                displayVideo(defaultStartIndex);
                showOrderSelection(defaultStartIndex);
                return;
            }
            let nextIndex = currentIndex;
            if (nextIndex >= videoOrder.length) {
                nextIndex = 0;
            }
            currentIndex = nextIndex;
            displayVideoByOrderIndex(currentIndex);
            showCurrentIndex();
            updateFavoriteStar();
        } else {
            updateFavoriteStar();
        }
        updateGridFavsButton();
    }

    function updateFavoriteStar() {
        if (!favoriteStar || videoOrder.length === 0) return;
        favoriteStar.classList.toggle('favorited', isCurrentVideoFavorited());
    }

    function buildFavoritesOrder() {
        return Array.from(favorites).sort((a, b) => a - b);
    }

    function isJumpSimilarMode() {
        return selectedOrder === 'jumpToSimilar';
    }

    function setStandardChromeVisible(visible) {
        document.body.classList.toggle('jump-similar-active', !visible);
        videoContainer.style.display = visible ? '' : 'none';
        fullscreenButton.style.display = visible ? 'block' : 'none';
        favoriteStar.style.display = visible ? 'flex' : 'none';
        const indexDisplay = document.getElementById('current-index');
        if (!visible) {
            indexDisplay.style.display = 'none';
        }
        if (similarLayout) {
            similarLayout.style.display = visible ? 'none' : 'flex';
        }
    }

    function ensureSimilarLayout() {
        if (similarLayout) {
            return similarLayout;
        }

        similarLayout = document.createElement('div');
        similarLayout.id = 'similar-layout';

        const parentTile = document.createElement('div');
        parentTile.id = 'similar-parent';
        parentTile.className = 'similar-tile similar-parent';
        parentTile.addEventListener('click', (event) => {
            event.stopPropagation();
            exitJumpToSimilarToClassic();
        });

        const childrenGrid = document.createElement('div');
        childrenGrid.id = 'similar-children';

        for (let slot = 0; slot < 6; slot += 1) {
            const childTile = document.createElement('div');
            childTile.className = 'similar-tile similar-child';
            childTile.dataset.childSlot = String(slot);
            childTile.addEventListener('click', (event) => {
                event.stopPropagation();
                const indices = topNeighbors[parentCatalogIndex] || [];
                const targetIndex = indices[slot];
                if (targetIndex !== undefined) {
                    setSimilarParent(targetIndex).catch(console.error);
                }
            });
            childrenGrid.appendChild(childTile);
        }

        similarLayout.appendChild(parentTile);
        similarLayout.appendChild(childrenGrid);
        similarLayout.style.display = 'none';
        document.body.appendChild(similarLayout);
        return similarLayout;
    }

    async function attachVideoToTile(tile, catalogIndex) {
        let video = tile.querySelector('video');
        if (!video) {
            video = document.createElement('video');
            video.autoplay = true;
            video.loop = true;
            video.muted = true;
            video.playsInline = true;
            tile.appendChild(video);
        }

        const loadVideo = async (bustCache) => {
            const url = await fetchVideoUrl(catalogIndex, bustCache);
            video.dataset.catalogIndex = String(catalogIndex);
            video.src = url;
            await video.play().catch(() => {});
        };

        video.onerror = () => {
            urlCache.delete(catalogIndex);
            loadVideo(true).catch(console.error);
        };

        await loadVideo(false);
    }

    async function setSimilarParent(catalogIndex) {
        parentCatalogIndex = catalogIndex;
        ensureSimilarLayout();

        const parentTile = similarLayout.querySelector('#similar-parent');
        const childTiles = similarLayout.querySelectorAll('.similar-child');
        const children = topNeighbors[catalogIndex] || [];

        await attachVideoToTile(parentTile, catalogIndex);

        childTiles.forEach((tile, slot) => {
            const childIndex = children[slot];
            if (childIndex === undefined) {
                tile.replaceChildren();
                return;
            }
            window.setTimeout(() => {
                attachVideoToTile(tile, childIndex).catch(console.error);
            }, 100 * (slot + 1));
        });
    }

    function enterJumpToSimilar(startCatalogIndex) {
        selectedOrder = 'jumpToSimilar';
        parentCatalogIndex = startCatalogIndex;
        setStandardChromeVisible(false);
        ensureSimilarLayout();
        similarLayout.style.display = 'flex';
        setSimilarParent(startCatalogIndex).catch(console.error);
    }

    function exitJumpToSimilarToClassic() {
        const catalogIndex = parentCatalogIndex;
        selectedOrder = 'classic';
        videoOrder = Array.from({ length: videoCount }, (_, i) => i);
        currentIndex = catalogIndex;
        setStandardChromeVisible(true);
        displayVideoByOrderIndex(currentIndex);
        showCurrentIndex();
        updateFavoriteStar();
    }

    function navigateSimilarParent(direction) {
        if (direction === 'forward') {
            parentCatalogIndex = (parentCatalogIndex + 1) % videoCount;
        } else if (direction === 'backward') {
            parentCatalogIndex = (parentCatalogIndex - 1 + videoCount) % videoCount;
        }
        setSimilarParent(parentCatalogIndex).catch(console.error);
    }

    function getCurrentCatalogIndex() {
        if (isJumpSimilarMode()) {
            return parentCatalogIndex;
        }
        if (videoOrder.length === 0) {
            return defaultStartIndex;
        }
        return getOriginalIndex(currentIndex);
    }

    function enterJumpToSimilarFromBrowsing() {
        if (!jumpToSimilarAvailable || orderSelectionShown) {
            return;
        }
        enterJumpToSimilar(getCurrentCatalogIndex());
    }

    function showOrderSelection(startVideoIndex) {
        const orderContainer = document.createElement('div');
        orderContainer.id = 'order-selection';
        orderContainer.style.cssText = [
            'position:fixed', 'top:0', 'left:0', 'width:100vw', 'height:100vh',
            'display:flex', 'flex-direction:column', 'justify-content:center', 'align-items:center',
            'gap:20px', 'z-index:10000001', 'background:rgba(0,0,0,0.3)',
        ].join(';');

        const buttonStyle = {
            padding: '20px 40px',
            fontSize: '24px',
            backgroundColor: 'rgba(255, 255, 255, 0.2)',
            color: 'white',
            border: '2px solid rgba(255, 255, 255, 0.5)',
            borderRadius: '10px',
            cursor: 'pointer',
            fontFamily: 'Arial, Helvetica, sans-serif',
            transition: 'all 0.3s ease',
            backdropFilter: 'blur(10px)',
        };

        function addOrderButton(label, orderType) {
            const btn = document.createElement('button');
            btn.textContent = label;
            Object.assign(btn.style, buttonStyle);
            btn.onmouseover = () => { btn.style.backgroundColor = 'rgba(255, 255, 255, 0.3)'; };
            btn.onmouseout = () => { btn.style.backgroundColor = 'rgba(255, 255, 255, 0.2)'; };
            btn.onclick = () => selectOrder(orderType, startVideoIndex, orderContainer);
            orderContainer.appendChild(btn);
        }

        addOrderButton('Classic', 'classic');
        if (similarityOrdersAvailable) {
            addOrderButton('Most Similar', 'mostSimilar');
            addOrderButton('Least Similar', 'leastSimilar');
        }
        if (favorites.size > 0) {
            addOrderButton(`Favorites (${favorites.size})`, 'favorites');
        }
        if (jumpToSimilarAvailable) {
            addOrderButton('Jump to Similar', 'jumpToSimilar');
        }

        document.body.appendChild(orderContainer);
        orderSelectionShown = true;
    }

    function selectOrder(orderType, startVideoIndex, orderContainer) {
        selectedOrder = orderType;

        orderContainer.remove();
        orderSelectionShown = false;

        if (orderType === 'jumpToSimilar') {
            enterJumpToSimilar(startVideoIndex);
            return;
        }

        if (orderType === 'classic') {
            videoOrder = Array.from({ length: videoCount }, (_, i) => i);
        } else if (orderType === 'mostSimilar') {
            videoOrder = [...mostSimilarOrder];
        } else if (orderType === 'leastSimilar') {
            videoOrder = [...leastSimilarOrder];
        } else if (orderType === 'favorites') {
            videoOrder = buildFavoritesOrder();
        }

        currentIndex = videoOrder.indexOf(startVideoIndex);
        if (currentIndex === -1) {
            currentIndex = 0;
        }

        setStandardChromeVisible(true);
        displayVideoByOrderIndex(currentIndex);
        showCurrentIndex();
        updateFavoriteStar();
    }

    const gridContainer = document.createElement('div');
    gridContainer.id = 'grid-container';
    gridContainer.style.cssText = [
        'position:fixed', 'top:0', 'left:0', 'width:100vw', 'height:100vh',
        'display:none', 'z-index:10000000', 'background:rgba(0,0,0,0.5)',
        'grid-template-columns:repeat(3,1fr)', 'grid-template-rows:repeat(4,1fr)',
    ].join(';');

    let gridFavsButton = null;

    function updateGridFavsButton() {
        if (!gridFavsButton) return;
        const enabled = favorites.size > 0;
        gridFavsButton.style.cursor = enabled ? 'pointer' : 'default';
        gridFavsButton.style.opacity = enabled ? '1' : '0.3';
        gridFavsButton.style.color = enabled ? 'white' : 'rgba(255, 255, 255, 0.5)';
    }

    const gridLayout = [
        [1, 2, 3],
        [4, 5, 6],
        [7, 8, 9],
        ['rand', 0, 'favs'],
    ];

    gridLayout.forEach((row) => {
        row.forEach((number) => {
            const button = document.createElement('button');
            button.className = 'grid-button';
            if (number === 'favs') {
                button.textContent = 'Favs';
                gridFavsButton = button;
            } else if (number === 'rand') {
                button.textContent = 'Rand';
            } else {
                button.textContent = String(number);
            }

            button.style.background = 'rgba(0, 0, 0, 0.1)';
            button.style.border = '1px solid white';
            button.style.color = 'white';
            button.style.cursor = 'pointer';
            button.style.display = 'flex';
            button.style.alignItems = 'center';
            button.style.justifyContent = 'center';
            if (number === 'favs' || number === 'rand') {
                button.style.fontSize = '1.2rem';
            }

            if (number === 'favs') {
                button.addEventListener('click', (e) => {
                    e.stopPropagation();
                    if (favorites.size === 0) return;
                    hideGrid();
                    selectedOrder = 'favorites';
                    videoOrder = buildFavoritesOrder();
                    currentIndex = 0;
                    displayVideoByOrderIndex(currentIndex);
                    showCurrentIndex();
                    updateFavoriteStar();
                });
            } else if (number !== '') {
                button.addEventListener('click', (e) => {
                    e.stopPropagation();
                    handleGridInput(number);
                });
            }

            gridContainer.appendChild(button);
        });
    });
    document.body.appendChild(gridContainer);
    updateGridFavsButton();

    function showGrid() {
        gridContainer.style.display = 'grid';
        gridVisible = true;
        updateGridFavsButton();
        clearTimeout(gridTimeout);
        gridTimeout = setTimeout(hideGrid, 3000);
    }

    function hideGrid() {
        gridContainer.style.display = 'none';
        gridVisible = false;
    }

    window.addEventListener('click', (e) => {
        if (
            e.target.closest('#order-selection')
            || e.target.closest('.grid-button')
            || e.target === gridContainer
            || e.target.id === 'fullscreen-button'
            || e.target.id === 'favorite-star'
            || e.target.closest('#sign-out-form')
        ) {
            return;
        }
        if (orderSelectionShown) return;
        if (isJumpSimilarMode()) return;
        showGrid();
    });

    favoriteStar.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleFavorite();
    });
    favoriteStar.addEventListener('touchend', (e) => {
        e.stopPropagation();
        e.preventDefault();
        toggleFavorite();
    });

    function handleGridInput(value) {
        if (value === 'rand') {
            hideGrid();
            setTimeout(() => {
                const randomOriginalIndex = Math.floor(Math.random() * videoCount);
                if (selectedOrder !== 'classic') {
                    selectedOrder = 'classic';
                    videoOrder = Array.from({ length: videoCount }, (_, i) => i);
                }
                currentIndex = videoOrder.indexOf(randomOriginalIndex);
                if (currentIndex === -1) currentIndex = 0;
                displayVideoByOrderIndex(currentIndex);
                showCurrentIndex();
                updateFavoriteStar();
            }, 100);
            return;
        }

        inputSequence += String(value);
        const indexDisplay = document.getElementById('current-index');
        indexDisplay.style.display = 'block';
        indexDisplay.textContent = inputSequence;
        indexDisplay.style.opacity = '1';
        indexDisplay.style.color = 'white';

        clearTimeout(inputTimeout);
        inputTimeout = setTimeout(() => {
            indexDisplay.style.opacity = '0';
            indexDisplay.style.display = 'none';

            const targetOriginalIndex = parseInt(inputSequence, 10) - 1;
            if (!Number.isNaN(targetOriginalIndex) && targetOriginalIndex >= 0 && targetOriginalIndex < videoCount) {
                currentIndex = videoOrder.indexOf(targetOriginalIndex);
                if (currentIndex === -1) currentIndex = 0;
                hideGrid();
                displayVideoByOrderIndex(currentIndex);
                showCurrentIndex();
            } else {
                indexDisplay.style.display = 'block';
                indexDisplay.textContent = String(parseInt(inputSequence, 10));
                indexDisplay.style.color = '#EB0000';
                indexDisplay.style.opacity = '1';
                setTimeout(() => {
                    indexDisplay.style.opacity = '0';
                    setTimeout(() => {
                        indexDisplay.style.display = 'none';
                        indexDisplay.style.color = 'white';
                    }, 1000);
                }, 1500);
                clearTimeout(gridTimeout);
                gridTimeout = setTimeout(hideGrid, 3000);
            }
            inputSequence = '';
        }, 1000);
    }

    function navigate(direction) {
        if (videoCount === 0 || videoOrder.length === 0) return;
        if (orderSelectionShown || gridVisible || isJumpSimilarMode()) return;

        if (direction === 'forward') {
            currentIndex = (currentIndex + 1) % videoOrder.length;
        } else if (direction === 'backward') {
            currentIndex = (currentIndex - 1 + videoOrder.length) % videoOrder.length;
        }
        displayVideoByOrderIndex(currentIndex);
        showCurrentIndex();
    }

    function showCurrentIndex() {
        const indexDisplay = document.getElementById('current-index');
        clearTimeout(indexDisplayTimeout);
        const originalIndex = getOriginalIndex(currentIndex);
        indexDisplay.style.display = 'block';
        indexDisplay.textContent = `${originalIndex + 1} of ${videoCount}`;
        indexDisplay.style.opacity = '1';
        indexDisplay.style.color = 'white';

        indexDisplayTimeout = setTimeout(() => {
            indexDisplay.style.opacity = '0';
            indexDisplayTimeout = setTimeout(() => {
                indexDisplay.style.display = 'none';
            }, 1000);
        }, 1000);
    }

    function syncFullscreenIcon() {
        const expandIcon = `${staticImgBase}arrows-alt_ffffff_64.png`;
        const compressIcon = `${staticImgBase}compress_ffffff_64.png`;
        fullscreenButton.style.backgroundImage = document.fullscreenElement
            ? `url('${compressIcon}')`
            : `url('${expandIcon}')`;
    }

    fullscreenButton.addEventListener('click', () => {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen().then(syncFullscreenIcon).catch(console.error);
        } else {
            document.exitFullscreen().then(syncFullscreenIcon).catch(console.error);
        }
    });

    document.addEventListener('fullscreenchange', syncFullscreenIcon);

    window.addEventListener('keydown', (event) => {
        if (isJumpSimilarMode()) {
            if (event.key === 'ArrowRight') {
                navigateSimilarParent('forward');
            } else if (event.key === 'ArrowLeft') {
                navigateSimilarParent('backward');
            } else if (event.key === 'Escape' && document.fullscreenElement) {
                document.exitFullscreen().then(syncFullscreenIcon).catch(console.error);
            }
            return;
        }
        if (event.key === 'ArrowRight') {
            navigate('forward');
        } else if (event.key === 'ArrowLeft') {
            navigate('backward');
        } else if (event.key === 'Escape') {
            if (document.fullscreenElement) {
                document.exitFullscreen().then(syncFullscreenIcon).catch(console.error);
            } else {
                syncFullscreenIcon();
            }
        } else if (event.key === ' ') {
            event.preventDefault();
            if (!orderSelectionShown && videoOrder.length > 0) {
                toggleFavorite();
            }
        } else if ((event.key === 'j' || event.key === 'J') && jumpToSimilarAvailable) {
            if (!orderSelectionShown && videoOrder.length > 0) {
                enterJumpToSimilarFromBrowsing();
            }
        }
    });

    let touchStartX = 0;
    window.addEventListener('touchstart', (event) => {
        touchStartX = event.changedTouches[0].screenX;
    }, false);
    window.addEventListener('touchend', (event) => {
        const touchEndX = event.changedTouches[0].screenX;
        const swipeThreshold = 50;
        if (orderSelectionShown || gridVisible || isJumpSimilarMode()) return;
        if (touchEndX < touchStartX - swipeThreshold) {
            navigate('forward');
        } else if (touchEndX > touchStartX + swipeThreshold) {
            navigate('backward');
        }
    }, false);

    if (videoCount > 0) {
        displayVideo(defaultStartIndex);
        showOrderSelection(defaultStartIndex);
    }
})();
