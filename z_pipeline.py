"""
Basketball Analytics Pipeline - Main Orchestrator
Config-driven, registry-based execution engine
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import time
from z_registry import get_module, load_config, BaseModule, list_modules


@dataclass
class PipelineMetrics:
    """Pipeline execution metrics"""
    frames_processed: int = 0
    total_time: float = 0.0
    module_stats: Dict[str, Dict] = field(default_factory=dict)
    events_by_type: Dict[str, int] = field(default_factory=dict)
    warnings: List[Dict] = field(default_factory=list)


class BasketballPipeline:
    """
    Config-driven pipeline orchestrator.
    
    Responsibilities:
    - Load config
    - Initialize modules from registry
    - Execute in order
    - Validate inputs/outputs
    - Collect metrics
    - Handle failures gracefully
    """
    
    def __init__(self, config_path: str = 'pipeline_config.yaml', 
                 verbose: bool = False, **module_kwargs):
        """
        Initialize pipeline.
        
        Args:
            config_path: Path to YAML config
            verbose: Enable detailed logging
            **module_kwargs: Arguments to pass to modules
        """
        self.verbose = verbose
        self.module_kwargs = module_kwargs
        
        # Initialize metrics FIRST (before _initialize_modules)
        self.metrics = PipelineMetrics()
        
        # Load config
        self.config = load_config(config_path)
        
        # Initialize modules (now metrics exists)
        self.modules: List[BaseModule] = []
        self._initialize_modules()
        
        if self.verbose:
            print(f"🏀 Pipeline Initialized")
            print(f"   Config: {config_path}")
            print(f"   Modules: {len(self.modules)} registered")
    
    def _initialize_modules(self):
        """Initialize all modules from config"""
        module_configs = self.config.get('modules', [])
        
        for mod_config in module_configs:
            name = mod_config['name']
            enabled = mod_config.get('enabled', True)
            
            if not enabled:
                if self.verbose:
                    print(f"⏭️  Module '{name}' disabled in config")
                continue
            
            try:
                # Get from registry
                module = get_module(name, **self.module_kwargs)
                self.modules.append(module)
                
                # Initialize stats
                self.metrics.module_stats[name] = {
                    'executions': 0,
                    'successes': 0,
                    'failures': 0,
                    'skipped': 0,
                    'total_time': 0.0
                }
                
                if self.verbose:
                    print(f"✅ Loaded: {name}")
            
            except KeyError as e:
                print(f"❌ Module not found in registry: {name}")
                print(f"   Available: {list_modules()}")
                raise
            except Exception as e:
                print(f"❌ Failed to initialize {name}: {e}")
                raise
    
    def process_frame(self, frame_data: Dict) -> Dict:
        """
        Process single frame through pipeline.
        
        Args:
            frame_data: Initial frame data dict
        
        Returns:
            Processed data dict
        """
        self.metrics.frames_processed += 1
        frame_start = time.time()
        
        if self.verbose:
            print(f"\n{'='*70}")
            print(f"Frame {frame_data.get('frame_id', '?')}")
            print(f"{'='*70}")
        
        data = frame_data.copy()
        
        # Execute modules in order
        for module in self.modules:
            module_start = time.time()
            
            # Update execution count
            self.metrics.module_stats[module.name]['executions'] += 1
            
            # Validate input
            is_valid, error = module.validate_input(data)
            if not is_valid:
                self.metrics.module_stats[module.name]['skipped'] += 1
                
                if self.verbose:
                    print(f"⏭️  {module.name:30s} SKIPPED: {error}")
                
                continue
            
            # Execute
            try:
                data = module.process(data)
                
                # Update metrics
                module_time = time.time() - module_start
                self.metrics.module_stats[module.name]['successes'] += 1
                self.metrics.module_stats[module.name]['total_time'] += module_time
                
                if self.verbose:
                    outputs = self._summarize_module_output(module, data)
                    print(f"✅ {module.name:30s} → {outputs} ({module_time*1000:.1f}ms)")
            
            except Exception as e:
                self.metrics.module_stats[module.name]['failures'] += 1
                
                warning = {
                    'module': module.name,
                    'frame_id': data.get('frame_id'),
                    'error': str(e)
                }
                self.metrics.warnings.append(warning)
                
                if self.verbose:
                    print(f"❌ {module.name:30s} FAILED: {e}")
                
                # Continue pipeline (fail-soft)
                continue
        
        # Frame complete
        frame_time = time.time() - frame_start
        self.metrics.total_time += frame_time
        
        # Count events
        for event in data.get('events', []):
            event_type = event.get('type', 'unknown')
            self.metrics.events_by_type[event_type] = \
                self.metrics.events_by_type.get(event_type, 0) + 1
        
        if self.verbose and data.get('events'):
            print(f"\n🎯 EVENTS ({len(data['events'])}):")
            for event in data['events']:
                print(f"   {event['type'].upper()}: Player {event.get('player_id')}")
        
        return data
    
    def _summarize_module_output(self, module: BaseModule, data: Dict) -> str:
        """Generate output summary for verbose logging"""
        outputs = module.get_outputs()
        
        if not outputs:
            return "no output"

        if module.name == "movement_classifier":
            states = []
            for pid, pdata in data.get('players', {}).items():
                s = pdata.get('movement_state', '?')
                states.append(f"P{pid}:{s}")
            return " | ".join(states[:5]) + ("..." if len(states)>5 else "")
            
        if module.name == "ball_tracking":
            owner = data.get('ball', {}).get('owner_id')
            detected = data.get('ball', {}).get('detected')
            return f"Ball: {'✓' if detected else 'x'}, Owner: {owner if owner else 'None'}"
        
        if module.name == "player_distance":
            matrix = data.get('distance_matrix', {})
            total_pairs = sum(len(v) for v in matrix.values())
            return f"matrix_pairs={total_pairs} (all-to-all)"
        
        if module.name == "speed_acceleration":
            speeds = [f"P{pid}:{p.get('speed', 0):.1f}" for pid, p in data['players'].items()]
            #return " | ".join(speeds[:4]) # İlk 4 oyuncunun hızını göster
            return data.get('speed_debug', 'No debug info')
        
        summary_parts = []
        for key in outputs:
            if key in data:
                value = data[key]
                if isinstance(value, dict):
                    summary_parts.append(f"{key}={len(value)}")
                elif isinstance(value, list):
                    summary_parts.append(f"{key}={len(value)}")
                else:
                    summary_parts.append(f"{key}=✓")
        
        return ", ".join(summary_parts) if summary_parts else "updated"
    
    def print_statistics(self):
        """Print comprehensive pipeline statistics"""
        print("\n" + "="*70)
        print("PIPELINE STATISTICS")
        print("="*70)
        
        print(f"\n📊 Overall:")
        print(f"   Frames processed: {self.metrics.frames_processed}")
        print(f"   Total time: {self.metrics.total_time:.2f}s")
        print(f"   Avg time/frame: {self.metrics.total_time/max(self.metrics.frames_processed,1)*1000:.1f}ms")
        
        print(f"\n📋 Module Performance:")
        print(f"{'Module':<30s} {'Exec':>8s} {'OK':>8s} {'Fail':>8s} {'Skip':>8s} {'Rate':>8s}")
        print("-"*70)
        
        for name, stats in self.metrics.module_stats.items():
            exec_count = stats['executions']
            if exec_count == 0:
                continue
            
            success_rate = stats['successes'] / exec_count * 100
            print(f"{name:<30s} {exec_count:>8d} {stats['successes']:>8d} "
                  f"{stats['failures']:>8d} {stats['skipped']:>8d} {success_rate:>7.1f}%")
        
        print("-"*70)
        
        if self.metrics.events_by_type:
            print(f"\n🎯 Events Detected:")
            for event_type, count in self.metrics.events_by_type.items():
                print(f"   {event_type:20s}: {count}")
        
        if self.metrics.warnings:
            print(f"\n⚠️  Warnings ({len(self.metrics.warnings)}):")
            for i, warning in enumerate(self.metrics.warnings[:5], 1):
                print(f"   {i}. [{warning['module']}] {warning['error']}")
            if len(self.metrics.warnings) > 5:
                print(f"   ... and {len(self.metrics.warnings)-5} more")
    
    def validate_pipeline(self) -> tuple[bool, List[str]]:
        """
        Validate pipeline configuration.
        
        Returns:
            (is_valid, error_messages)
        """
        errors = []
        
        # Check module dependencies
        all_outputs = set()
        
        for module in self.modules:
            requirements = module.get_requirements()
            
            # Check if requirements are satisfied by previous modules
            for req in requirements:
                if req not in all_outputs:
                    # Check if it's an initial input
                    if req not in ['frame', 'timestamp', 'M', 'M1', 'map_2d', 'frame_id']:
                        errors.append(
                            f"Module '{module.name}' requires '{req}' "
                            f"but no previous module produces it"
                        )
            
            # Add this module's outputs
            all_outputs.update(module.get_outputs())
        
        return len(errors) == 0, errors
    
    def get_module_order(self) -> List[str]:
        """Get list of module names in execution order"""
        return [m.name for m in self.modules]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_pipeline_from_config(config_path: str = 'pipeline_config.yaml',
                                verbose: bool = False,
                                **module_kwargs) -> BasketballPipeline:
    """
    Factory function to create pipeline from config.
    
    Args:
        config_path: Path to config file
        verbose: Enable verbose logging
        **module_kwargs: Arguments for module initialization
    
    Returns:
        Initialized pipeline
    """
    return BasketballPipeline(config_path, verbose, **module_kwargs)


def validate_pipeline_config(config_path: str = 'pipeline_config.yaml'):
    """
    Validate pipeline configuration without running.
    
    Prints validation results.
    """
    print("🔍 Validating Pipeline Configuration...")
    print("="*70)
    
    try:
        # Try to create pipeline
        pipeline = BasketballPipeline(config_path, verbose=False)
        
        print(f"\n✅ Config loaded successfully")
        print(f"   Modules: {len(pipeline.modules)}")
        
        # Validate dependencies
        is_valid, errors = pipeline.validate_pipeline()
        
        if is_valid:
            print(f"\n✅ Pipeline validation PASSED")
            print(f"\nExecution order:")
            for i, name in enumerate(pipeline.get_module_order(), 1):
                print(f"  {i}. {name}")
        else:
            print(f"\n❌ Pipeline validation FAILED")
            print(f"\nErrors:")
            for error in errors:
                print(f"  - {error}")
        
        return is_valid
    
    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
        return False


if __name__ == "__main__":
    print("🏀 Basketball Analytics Pipeline")
    print("="*70)
    
    # Validate config
    validate_pipeline_config()
    
    print("\n✅ Pipeline orchestrator ready!")
