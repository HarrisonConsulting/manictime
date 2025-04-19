"""Advanced pagination handling for large datasets."""
import logging
import math
import time
from typing import Dict, Any, List, Optional, Callable, Generator, TypeVar, Generic, Iterator
from datetime import datetime, timedelta
import concurrent.futures
from dataclasses import dataclass

logger = logging.getLogger("manictime.pagination")

T = TypeVar('T')


@dataclass
class PageInfo:
    """Information about a page of data"""
    page_number: int
    page_size: int
    total_items: Optional[int]
    total_pages: Optional[int]
    has_next: bool


class PaginatedResult(Generic[T]):
    """Container for paginated results with metadata"""
    
    def __init__(self, 
                items: List[T],
                page_info: PageInfo):
        """
        Initialize paginated result
        
        Args:
            items: List of items in the current page
            page_info: Pagination information
        """
        self.items = items
        self.page_info = page_info
        
    def __len__(self) -> int:
        """Get number of items in current page"""
        return len(self.items)
        
    def __iter__(self) -> Iterator[T]:
        """Iterate over items in current page"""
        return iter(self.items)
        
    def __getitem__(self, index: int) -> T:
        """Get item by index"""
        return self.items[index]


class PagedIterator(Generic[T]):
    """Iterator for efficiently retrieving all pages of data"""
    
    def __init__(self,
                fetch_page: Callable[[int, int], PaginatedResult[T]],
                page_size: int = 100,
                max_pages: Optional[int] = None,
                start_page: int = 0):
        """
        Initialize paged iterator
        
        Args:
            fetch_page: Function to fetch a page of data
            page_size: Number of items per page
            max_pages: Maximum number of pages to fetch (None for unlimited)
            start_page: Page number to start from
        """
        self.fetch_page = fetch_page
        self.page_size = page_size
        self.max_pages = max_pages
        self.current_page = start_page
        self.exhausted = False
        
    def __iter__(self) -> 'PagedIterator[T]':
        """Return self as iterator"""
        return self
        
    def __next__(self) -> PaginatedResult[T]:
        """Get next page of results"""
        if self.exhausted:
            raise StopIteration
            
        if self.max_pages is not None and self.current_page >= self.max_pages:
            raise StopIteration
            
        result = self.fetch_page(self.current_page, self.page_size)
        self.current_page += 1
        
        if not result.page_info.has_next:
            self.exhausted = True
            
        return result


class TimeRangePaginator:
    """Paginator for time-based data using date ranges"""
    
    def __init__(self,
                fetch_fn: Callable[[datetime, datetime], List[T]],
                start_date: datetime,
                end_date: datetime,
                chunk_size: timedelta = timedelta(days=7)):
        """
        Initialize time range paginator
        
        Args:
            fetch_fn: Function to fetch data for a date range
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            chunk_size: Size of each time chunk
        """
        self.fetch_fn = fetch_fn
        self.start_date = start_date
        self.end_date = end_date
        self.chunk_size = chunk_size
        
    def __iter__(self) -> Generator[List[T], None, None]:
        """Iterate through time chunks"""
        current_start = self.start_date
        
        while current_start <= self.end_date:
            current_end = min(current_start + self.chunk_size, self.end_date)
            
            logger.debug(f"Fetching data from {current_start} to {current_end}")
            yield self.fetch_fn(current_start, current_end)
            
            current_start = current_end + timedelta(seconds=1)
            
    def get_all(self) -> List[T]:
        """
        Get all items across all time chunks
        
        Returns:
            Combined list of all items
        """
        all_items = []
        for items in self:
            all_items.extend(items)
        return all_items
        
    def get_all_parallel(self, max_workers: int = 5) -> List[T]:
        """
        Get all items across all time chunks in parallel
        
        Args:
            max_workers: Maximum number of parallel workers
            
        Returns:
            Combined list of all items
        """
        # Generate time chunks
        chunks = []
        current_start = self.start_date
        
        while current_start <= self.end_date:
            current_end = min(current_start + self.chunk_size, self.end_date)
            chunks.append((current_start, current_end))
            current_start = current_end + timedelta(seconds=1)
            
        # Fetch data in parallel
        all_items = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Create a mapping of futures to their chunk info for better logging
            future_to_chunk = {
                executor.submit(self.fetch_fn, start, end): (start, end)
                for start, end in chunks
            }
            
            for future in concurrent.futures.as_completed(future_to_chunk):
                start, end = future_to_chunk[future]
                try:
                    items = future.result()
                    logger.debug(f"Retrieved {len(items)} items for {start} to {end}")
                    all_items.extend(items)
                except Exception as e:
                    logger.error(f"Error fetching {start} to {end}: {str(e)}")
                    
        return all_items


class BulkOperationManager:
    """Manager for performing bulk operations with batching and retry logic"""
    
    def __init__(self,
                batch_size: int = 100,
                max_retries: int = 3,
                retry_delay: float = 1.0,
                parallel: bool = False,
                max_workers: int = 5):
        """
        Initialize bulk operation manager
        
        Args:
            batch_size: Number of items per batch
            max_retries: Maximum number of retries for failed operations
            retry_delay: Delay between retries in seconds
            parallel: Whether to process batches in parallel
            max_workers: Maximum number of parallel workers
        """
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.parallel = parallel
        self.max_workers = max_workers
        
    def _create_batches(self, items: List[T]) -> List[List[T]]:
        """
        Split items into batches
        
        Args:
            items: List of items to batch
            
        Returns:
            List of batches
        """
        return [
            items[i:i + self.batch_size]
            for i in range(0, len(items), self.batch_size)
        ]
        
    def _process_batch_with_retry(self, 
                                operation: Callable[[List[T]], Any],
                                batch: List[T]) -> Any:
        """
        Process a batch with retry logic
        
        Args:
            operation: Function to process the batch
            batch: Batch of items
            
        Returns:
            Result of the operation
            
        Raises:
            Exception: If all retries fail
        """
        retries = 0
        last_error = None
        
        while retries <= self.max_retries:
            try:
                return operation(batch)
            except Exception as e:
                last_error = e
                retries += 1
                
                if retries <= self.max_retries:
                    delay = self.retry_delay * (2 ** (retries - 1))  # Exponential backoff
                    logger.warning(f"Batch operation failed, retrying in {delay:.2f}s (retry {retries}/{self.max_retries}): {str(e)}")
                    time.sleep(delay)
                    
        # If we get here, all retries failed
        logger.error(f"Batch operation failed after {self.max_retries} retries: {str(last_error)}")
        raise last_error
        
    def process(self, items: List[T], operation: Callable[[List[T]], Any]) -> List[Any]:
        """
        Process items in batches
        
        Args:
            items: Items to process
            operation: Function to process each batch
            
        Returns:
            List of results for each batch
        """
        batches = self._create_batches(items)
        results = []
        
        if self.parallel:
            # Process batches in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_batch = {
                    executor.submit(
                        self._process_batch_with_retry, operation, batch
                    ): batch
                    for batch in batches
                }
                
                for future in concurrent.futures.as_completed(future_to_batch):
                    batch = future_to_batch[future]
                    try:
                        result = future.result()
                        results.append(result)
                        logger.debug(f"Processed batch of {len(batch)} items")
                    except Exception as e:
                        logger.error(f"Batch processing failed: {str(e)}")
                        raise
        else:
            # Process batches sequentially
            for batch in batches:
                try:
                    result = self._process_batch_with_retry(operation, batch)
                    results.append(result)
                    logger.debug(f"Processed batch of {len(batch)} items")
                except Exception as e:
                    logger.error(f"Batch processing failed: {str(e)}")
                    raise
                    
        return results